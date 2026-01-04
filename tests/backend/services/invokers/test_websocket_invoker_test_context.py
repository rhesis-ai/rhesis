"""Tests for WebSocket endpoint invoker with test execution context."""

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.services.invokers.websocket_invoker import WebSocketEndpointInvoker


class TestWebSocketInvokerTestContext:
    """Test WebSocket invoker with test execution context propagation."""

    def test_automatic_tracing_property(self):
        """Test that WebSocketEndpointInvoker has automatic_tracing set to False."""
        invoker = WebSocketEndpointInvoker()

        assert hasattr(invoker, "automatic_tracing")
        assert invoker.automatic_tracing is False

    @pytest.mark.asyncio
    async def test_invoke_accepts_test_execution_context(
        self, mock_db, sample_endpoint_websocket, sample_input_data
    ):
        """Test that invoke method accepts test_execution_context parameter."""
        invoker = WebSocketEndpointInvoker()

        test_execution_context = {
            "test_run_id": str(uuid4()),
            "test_result_id": str(uuid4()),
            "test_id": str(uuid4()),
            "test_configuration_id": str(uuid4()),
        }

        mock_messages = [
            json.dumps({"message": "Success", "conversation_id": "conv-123"}),
            json.dumps({"message": "response ended"}),
        ]

        mock_websocket = AsyncMock()
        mock_websocket.__aenter__.return_value = mock_websocket
        mock_websocket.__aexit__.return_value = None
        mock_websocket.send = AsyncMock()

        async def mock_iter():
            for msg in mock_messages:
                yield msg

        mock_websocket.__aiter__ = lambda self: mock_iter()

        with patch(
            "rhesis.backend.app.services.invokers.websocket_invoker.connect",
            return_value=mock_websocket,
        ):
            # Should not raise error when test_execution_context is provided
            result = await invoker.invoke(
                mock_db,
                sample_endpoint_websocket,
                sample_input_data,
                test_execution_context=test_execution_context,
            )

        assert result["output"] == "Success"

    @pytest.mark.asyncio
    async def test_invoke_works_without_test_execution_context(
        self, mock_db, sample_endpoint_websocket, sample_input_data
    ):
        """Test that invoke works when test_execution_context is None or omitted."""
        invoker = WebSocketEndpointInvoker()

        mock_messages = [
            json.dumps({"message": "Success"}),
            json.dumps({"message": "response ended"}),
        ]

        mock_websocket = AsyncMock()
        mock_websocket.__aenter__.return_value = mock_websocket
        mock_websocket.__aexit__.return_value = None
        mock_websocket.send = AsyncMock()

        async def mock_iter():
            for msg in mock_messages:
                yield msg

        mock_websocket.__aiter__ = lambda self: mock_iter()

        with patch(
            "rhesis.backend.app.services.invokers.websocket_invoker.connect",
            return_value=mock_websocket,
        ):
            # Test with None
            result = await invoker.invoke(
                mock_db,
                sample_endpoint_websocket,
                sample_input_data,
                test_execution_context=None,
            )
            assert result["output"] == "Success"

            # Test without the parameter (backward compatibility)
            result = await invoker.invoke(
                mock_db,
                sample_endpoint_websocket,
                sample_input_data,
            )
            assert result["output"] == "Success"
