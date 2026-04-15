"""Tests for Dispatcher."""

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
    routing = {"proj:dev": ["conn-1"]}
    counter = {"proj:dev": 0}

    def get_key(project_id, environment):
        return f"{project_id}:{environment.lower()}"

    def resolve_route(project_id, environment):
        key = get_key(project_id, environment)
        pool = routing.get(key)
        if not pool:
            return None
        live = [c for c in pool if c in connections]
        if not live:
            return None
        idx = counter.get(key, 0) % len(live)
        counter[key] = idx + 1
        return live[idx]

    remove_connection_route = Mock()

    return Dispatcher(
        connections=connections,
        resolve_route=resolve_route,
        result_store=result_store,
        get_connection_key=get_key,
        remove_connection_route=remove_connection_route,
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
        result = await dispatcher.send_test_request("unknown", "dev", "run-1", "my_func", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_send_error(self, dispatcher, mock_websocket):
        mock_websocket.send_json.side_effect = Exception("broken")
        result = await dispatcher.send_test_request("proj", "dev", "run-1", "my_func", {})
        assert result is False
        dispatcher._remove_connection_route.assert_called()


class TestDispatchRetry:
    """Tests for pool-level retry on send failure."""

    @pytest.mark.asyncio
    async def test_retries_with_next_connection_on_failure(self, result_store):
        ws_bad = Mock()
        ws_bad.send_json = AsyncMock(side_effect=Exception("dead"))
        ws_good = Mock()
        ws_good.send_json = AsyncMock()

        connections = {"c1": ws_bad, "c2": ws_good}
        call_count = 0

        def resolve_route(project_id, environment):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "c1"
            return "c2"

        remove_route = Mock()

        dispatcher = Dispatcher(
            connections=connections,
            resolve_route=resolve_route,
            result_store=result_store,
            get_connection_key=lambda p, e: f"{p}:{e}",
            remove_connection_route=remove_route,
        )

        result = await dispatcher.send_test_request("proj", "dev", "run-1", "my_func", {"k": "v"})

        assert result is True
        ws_bad.send_json.assert_called_once()
        ws_good.send_json.assert_called_once()
        remove_route.assert_called_once_with("proj:dev", "c1")

    @pytest.mark.asyncio
    async def test_gives_up_after_max_attempts(self, result_store):
        ws = Mock()
        ws.send_json = AsyncMock(side_effect=Exception("always fails"))
        connections = {"c1": ws}

        def resolve_route(project_id, environment):
            return "c1"

        remove_route = Mock()

        dispatcher = Dispatcher(
            connections=connections,
            resolve_route=resolve_route,
            result_store=result_store,
            get_connection_key=lambda p, e: f"{p}:{e}",
            remove_connection_route=remove_route,
        )

        result = await dispatcher.send_test_request("proj", "dev", "run-1", "my_func", {})

        assert result is False
        assert remove_route.call_count == 3


class TestSendMetricByConnection:
    @pytest.mark.asyncio
    async def test_sends_metric_successfully(self, dispatcher, mock_websocket):
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
    async def test_returns_result_on_success(self, dispatcher, result_store, mock_websocket):
        async def fake_send_json(msg):
            result_store.resolve_test_result("run-1", {"status": "success", "output": "hello"})

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
        result = await dispatcher.send_and_await_result("unknown", "dev", "run-1", "my_func", {})
        assert result["error"] == "send_failed"
