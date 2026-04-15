"""Tests for Dispatcher."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from rhesis.backend.app.services.connector.dispatcher import Dispatcher
from rhesis.backend.app.services.connector.result_store import ResultStore


@pytest.fixture
def result_store():
    tracker = MagicMock(return_value=MagicMock())
    return ResultStore(track_background_task=tracker)


@pytest.fixture
def mock_websocket():
    ws = Mock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def dispatcher(result_store, mock_websocket):
    connections = {"conn-1": mock_websocket}
    routing = {"proj:dev": "conn-1"}

    def get_key(project_id, environment):
        return f"{project_id}:{environment.lower()}"

    return Dispatcher(
        connections=connections,
        project_routing=routing,
        result_store=result_store,
        get_connection_key=get_key,
    )


class TestSendTestRequest:
    @pytest.mark.asyncio
    async def test_sends_successfully(self, dispatcher, mock_websocket):
        result = await dispatcher.send_test_request(
            "proj", "dev", "run-1", "my_func", {"key": "val"}
        )
        assert result is True
        mock_websocket.send_json.assert_called_once()
        payload = mock_websocket.send_json.call_args[0][0]
        assert payload["type"] == "execute_test"
        assert payload["function_name"] == "my_func"

    @pytest.mark.asyncio
    async def test_returns_false_when_not_connected(self, dispatcher):
        result = await dispatcher.send_test_request(
            "unknown", "dev", "run-1", "my_func", {}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_send_error(
        self, dispatcher, mock_websocket
    ):
        mock_websocket.send_json.side_effect = Exception("broken")
        result = await dispatcher.send_test_request(
            "proj", "dev", "run-1", "my_func", {}
        )
        assert result is False


class TestSendMetricByConnection:
    @pytest.mark.asyncio
    async def test_sends_metric_successfully(
        self, dispatcher, mock_websocket
    ):
        result = await dispatcher.send_metric_by_connection(
            "conn-1", "metric-1", "accuracy", {"input": "data"}
        )
        assert result is True
        payload = mock_websocket.send_json.call_args[0][0]
        assert payload["type"] == "execute_metric"
        assert payload["metric_name"] == "accuracy"

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_connection(self, dispatcher):
        result = await dispatcher.send_metric_by_connection(
            "unknown-conn", "metric-1", "accuracy", {}
        )
        assert result is False


class TestSendAndAwaitResult:
    @pytest.mark.asyncio
    async def test_returns_result_on_success(
        self, dispatcher, result_store, mock_websocket
    ):
        async def fake_send_json(msg):
            result_store.resolve_test_result(
                "run-1", {"status": "success", "output": "hello"}
            )

        mock_websocket.send_json = AsyncMock(side_effect=fake_send_json)

        result = await dispatcher.send_and_await_result(
            "proj", "dev", "run-1", "my_func", {}, timeout=5.0
        )
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_returns_timeout_error(self, dispatcher):
        result = await dispatcher.send_and_await_result(
            "proj", "dev", "run-1", "my_func", {}, timeout=0.01
        )
        assert result["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_returns_send_failed_when_not_connected(self, dispatcher):
        result = await dispatcher.send_and_await_result(
            "unknown", "dev", "run-1", "my_func", {}
        )
        assert result["error"] == "send_failed"
