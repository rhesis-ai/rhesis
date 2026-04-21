"""Tests for ResultStore."""

import asyncio
from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.services.connector.result_store import ResultStore


@pytest.fixture
def store():
    tracker = MagicMock(return_value=MagicMock())
    return ResultStore(track_background_task=tracker)


class TestResolveTestResult:
    @pytest.mark.asyncio
    async def test_stores_result_and_fires_event(self, store: ResultStore):
        event = store.create_event("run-1")
        store.resolve_test_result("run-1", {"status": "success"})

        assert store.get_test_result("run-1") == {"status": "success"}
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_ignores_cancelled_run(self, store: ResultStore):
        store.cleanup_test_result("run-1")
        store.resolve_test_result("run-1", {"status": "success"})
        assert store.get_test_result("run-1") is None

    @pytest.mark.asyncio
    async def test_publishes_to_redis_when_available(self, store: ResultStore):
        with patch(
            "rhesis.backend.app.services.connector.result_store.redis_manager"
        ) as mock_redis:
            mock_redis.is_available = True
            store.resolve_test_result("run-1", {"status": "success"})
            store._track_background_task.assert_called_once()


class TestResolveMetricResult:
    @pytest.mark.asyncio
    async def test_stores_metric_and_fires_event(self, store: ResultStore):
        event = store.create_event("metric-1")
        store.resolve_metric_result("metric-1", {"status": "success"})

        assert store.get_metric_result("metric-1") == {"status": "success"}
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_ignores_cancelled_metric(self, store: ResultStore):
        store.cleanup_metric_result("metric-1")
        store.resolve_metric_result("metric-1", {"status": "success"})
        assert store.get_metric_result("metric-1") is None


class TestCleanup:
    def test_cleanup_test_marks_cancelled(self, store: ResultStore):
        store._test_results["run-1"] = {"status": "success"}
        store.cleanup_test_result("run-1")

        assert "run-1" not in store._test_results
        assert "run-1" in store._cancelled_tests

    def test_cleanup_metric_marks_cancelled(self, store: ResultStore):
        store._metric_results["m-1"] = {"status": "success"}
        store.cleanup_metric_result("m-1")

        assert "m-1" not in store._metric_results
        assert "m-1" in store._cancelled_metrics

    def test_trim_cancelled_keeps_newest(self, store: ResultStore):
        cancelled = OrderedDict((str(i), True) for i in range(100))
        trimmed = ResultStore._trim_cancelled(cancelled, keep=10, label="test")
        assert len(trimmed) == 10
        assert list(trimmed.keys()) == [str(i) for i in range(90, 100)]


class TestEventManagement:
    def test_create_and_remove_event(self, store: ResultStore):
        event = store.create_event("run-1")
        assert isinstance(event, asyncio.Event)
        assert "run-1" in store._result_events

        store.remove_event("run-1")
        assert "run-1" not in store._result_events

    def test_remove_nonexistent_event_is_noop(self, store: ResultStore):
        store.remove_event("nonexistent")


class TestPublishRpcResponse:
    @pytest.mark.asyncio
    async def test_publish_success(self, store: ResultStore):
        with patch(
            "rhesis.backend.app.services.connector.result_store.redis_manager"
        ) as mock_redis:
            mock_redis.client = AsyncMock()
            await store._publish_rpc_response("run-1", {"status": "ok"})
            mock_redis.client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_handles_error(self, store: ResultStore):
        with patch(
            "rhesis.backend.app.services.connector.result_store.redis_manager"
        ) as mock_redis:
            mock_redis.client = AsyncMock()
            mock_redis.client.publish.side_effect = Exception("boom")
            await store._publish_rpc_response("run-1", {"status": "ok"})
