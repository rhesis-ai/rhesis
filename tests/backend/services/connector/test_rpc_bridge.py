"""Tests for RpcBridge."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from rhesis.backend.app.services.connector.rpc_bridge import RpcBridge


@pytest.fixture
def mock_websocket():
    ws = Mock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def bridge(mock_websocket):
    connections = {"conn-1": mock_websocket}
    routing = {"proj:dev": "conn-1"}

    def get_key(project_id, environment):
        return f"{project_id}:{environment.lower()}"

    cleanup = Mock()

    return RpcBridge(
        worker_id="test-worker-1",
        connections=connections,
        project_routing=routing,
        get_connection_key=get_key,
        cleanup_project_routing=cleanup,
    )


class TestHandleRpcRequest:
    @pytest.mark.asyncio
    async def test_forwards_test_to_sdk(self, bridge, mock_websocket):
        request = {
            "request_id": "rpc-1",
            "request_type": "execute_test",
            "project_id": "proj",
            "environment": "dev",
            "function_name": "my_func",
            "inputs": {"key": "val"},
        }
        await bridge._handle_rpc_request(request)
        mock_websocket.send_json.assert_called_once()
        payload = mock_websocket.send_json.call_args[0][0]
        assert payload["type"] == "execute_test"
        assert payload["function_name"] == "my_func"

    @pytest.mark.asyncio
    async def test_forwards_metric_to_sdk(self, bridge, mock_websocket):
        request = {
            "request_id": "rpc-2",
            "request_type": "execute_metric",
            "project_id": "proj",
            "environment": "dev",
            "metric_name": "accuracy",
            "inputs": {},
        }
        await bridge._handle_rpc_request(request)
        mock_websocket.send_json.assert_called_once()
        payload = mock_websocket.send_json.call_args[0][0]
        assert payload["type"] == "execute_metric"

    @pytest.mark.asyncio
    async def test_forwards_metric_by_connection_id(
        self, bridge, mock_websocket
    ):
        request = {
            "request_id": "rpc-3",
            "request_type": "execute_metric",
            "connection_id": "conn-1",
            "metric_name": "accuracy",
            "inputs": {},
        }
        await bridge._handle_rpc_request(request)
        mock_websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_publishes_error_when_connection_missing(self, bridge):
        request = {
            "request_id": "rpc-4",
            "connection_id": "unknown-conn",
            "metric_name": "accuracy",
            "inputs": {},
        }
        with patch.object(
            bridge, "_publish_error_response", new_callable=AsyncMock
        ) as mock_pub:
            await bridge._handle_rpc_request(request)
            mock_pub.assert_called_once()

    @pytest.mark.asyncio
    async def test_publishes_error_when_routing_missing(self, bridge):
        request = {
            "request_id": "rpc-5",
            "project_id": "unknown",
            "environment": "dev",
            "function_name": "my_func",
            "inputs": {},
        }
        with patch.object(
            bridge, "_publish_error_response", new_callable=AsyncMock
        ) as mock_pub:
            await bridge._handle_rpc_request(request)
            mock_pub.assert_called_once()


class TestForwardMessageToSdk:
    @pytest.mark.asyncio
    async def test_cleans_stale_routing_on_send_error(
        self, bridge, mock_websocket
    ):
        mock_websocket.send_json.side_effect = Exception("broken pipe")
        with patch.object(
            bridge, "_publish_error_response", new_callable=AsyncMock
        ):
            await bridge._forward_to_sdk(
                "rpc-1", "proj:dev", mock_websocket, "my_func", {}
            )
        bridge._cleanup_project_routing.assert_called_once_with("proj:dev")


class TestPublishErrorResponse:
    @pytest.mark.asyncio
    async def test_publishes_via_redis(self, bridge):
        with patch(
            "rhesis.backend.app.services.connector.rpc_bridge.redis_manager"
        ) as mock_redis:
            mock_redis.is_available = True
            mock_redis.client = AsyncMock()
            await bridge._publish_error_response(
                "rpc-1", "proj:dev", "some error"
            )
            mock_redis.client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_noop_when_redis_unavailable(self, bridge):
        with patch(
            "rhesis.backend.app.services.connector.rpc_bridge.redis_manager"
        ) as mock_redis:
            mock_redis.is_available = False
            await bridge._publish_error_response(
                "rpc-1", "proj:dev", "some error"
            )


class TestListenSkipsWithoutRedis:
    @pytest.mark.asyncio
    async def test_returns_immediately_without_redis(self, bridge):
        with patch(
            "rhesis.backend.app.services.connector.rpc_bridge.redis_manager"
        ) as mock_redis:
            mock_redis.is_available = False
            await bridge.listen()
