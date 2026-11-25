"""One call timeout for every connection type, enforced as a total deadline."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from rhesis.backend.app.services.invokers.common.timeouts import (
    SDK_FUNCTION_TIMEOUT,
    call_timeout,
)
from rhesis.backend.app.services.invokers.websocket_invoker import WebSocketEndpointInvoker


@pytest.mark.parametrize(
    "connection_type,expected",
    [("REST", 30.0), ("WebSocket", 30.0), ("SDK", SDK_FUNCTION_TIMEOUT), ("GRPC", 30.0)],
)
def test_default_per_connection_type(connection_type, expected):
    endpoint = SimpleNamespace(timeout_seconds=None, connection_type=connection_type)
    assert call_timeout(endpoint) == expected


def test_endpoint_timeout_wins():
    endpoint = SimpleNamespace(timeout_seconds=3600, connection_type="SDK")
    assert call_timeout(endpoint) == 3600.0


@pytest.mark.asyncio
async def test_websocket_call_stops_at_the_endpoint_timeout():
    """The WebSocket invoker used to wait forever on a stream that never ended."""
    endpoint = Mock(
        timeout_seconds=1,
        connection_type="WebSocket",
        url="wss://agent.example.com/ws",
        auth_type=None,
    )
    endpoint.name = "slow"
    invoker = WebSocketEndpointInvoker()

    async def _never_ends(*_args, **_kwargs):
        await asyncio.sleep(30)

    with patch.object(invoker, "_async_invoke", side_effect=_never_ends):
        result = await asyncio.wait_for(
            invoker.invoke(Mock(), endpoint, {"input": "hi"}), timeout=10
        )

    assert result.error_type == "call_timeout"
    assert result.output.startswith("agent.example.com did not finish within 1 second.")
