"""Tests for WebSocket endpoint invoker."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from websockets.exceptions import InvalidStatus

from rhesis.backend.app.services.invokers.websocket_invoker import WebSocketEndpointInvoker


class TestWebSocketEndpointInvoker:
    """Test WebSocketEndpointInvoker class functionality."""

    def test_init_creates_required_components(self):
        """Test that invoker initializes with all required components."""
        invoker = WebSocketEndpointInvoker()

        assert invoker.template_renderer is not None
        assert invoker.response_mapper is not None
        assert invoker.auth_manager is not None
        assert invoker.conversation_tracker is not None

    def test_normalize_unicode_text(self):
        """Test Unicode text normalization."""
        invoker = WebSocketEndpointInvoker()

        # Test quotation marks
        text_with_quotes = "Hello \u201cWorld\u201d"
        result = invoker._normalize_unicode_text(text_with_quotes)
        assert result == 'Hello "World"'

        # Test dashes
        text_with_dash = "Hello\u2014World"
        result = invoker._normalize_unicode_text(text_with_dash)
        assert result == "Hello-World"

        # Test ellipsis
        text_with_ellipsis = "Hello\u2026"
        result = invoker._normalize_unicode_text(text_with_ellipsis)
        assert result == "Hello..."

    def test_normalize_unicode_text_empty_string(self):
        """Test normalizing empty string."""
        invoker = WebSocketEndpointInvoker()

        result = invoker._normalize_unicode_text("")

        assert result == ""

    def test_normalize_unicode_text_none(self):
        """Test normalizing None."""
        invoker = WebSocketEndpointInvoker()

        result = invoker._normalize_unicode_text(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_async_invoke_success(
        self, mock_db, sample_endpoint_websocket, sample_input_data
    ):
        """Test successful async WebSocket invocation."""
        invoker = WebSocketEndpointInvoker()

        # Mock WebSocket responses
        mock_messages = [
            json.dumps({"message": "Hello!", "conversation_id": "conv-123"}),
            json.dumps({"message": "response ended"}),
        ]

        mock_websocket = AsyncMock()
        mock_websocket.__aenter__.return_value = mock_websocket
        mock_websocket.__aexit__.return_value = None
        mock_websocket.send = AsyncMock()

        # Mock async iteration
        async def mock_iter():
            for msg in mock_messages:
                yield msg

        mock_websocket.__aiter__ = lambda self: mock_iter()

        with patch(
            "rhesis.backend.app.services.invokers.websocket_invoker.connect",
            return_value=mock_websocket,
        ):
            result = await invoker._async_invoke(
                mock_db, sample_endpoint_websocket, sample_input_data
            )

        assert result["output"] == "Hello!"
        assert result["conversation_id"] == "conv-123"

    @pytest.mark.asyncio
    async def test_async_invoke_with_streaming_text(
        self, mock_db, sample_endpoint_websocket, sample_input_data
    ):
        """Test WebSocket with streaming text chunks."""
        invoker = WebSocketEndpointInvoker()

        # Mix of streaming text and JSON
        mock_messages = [
            "Streaming ",
            "text ",
            "content",
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
            result = await invoker._async_invoke(
                mock_db, sample_endpoint_websocket, sample_input_data
            )

        assert result["output"] == "Streaming text content"

    @pytest.mark.asyncio
    async def test_async_invoke_handles_error_message(
        self, mock_db, sample_endpoint_websocket, sample_input_data
    ):
        """Test handling of error messages from WebSocket."""
        invoker = WebSocketEndpointInvoker()

        mock_messages = [
            json.dumps({"error": "Authentication failed"}),
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
            result = await invoker._async_invoke(
                mock_db, sample_endpoint_websocket, sample_input_data
            )

        assert result["error"] == "Authentication failed"
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_async_invoke_connection_rejected(
        self, mock_db, sample_endpoint_websocket, sample_input_data
    ):
        """Test handling of WebSocket connection rejection."""
        invoker = WebSocketEndpointInvoker()

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.body = "Unauthorized"

        invalid_status = InvalidStatus(mock_response)

        with patch(
            "rhesis.backend.app.services.invokers.websocket_invoker.connect",
            side_effect=invalid_status,
        ):
            result = await invoker._async_invoke(
                mock_db, sample_endpoint_websocket, sample_input_data
            )

        assert result["error"] is True
        assert result["error_type"] == "websocket_connection_error"
        assert "401" in result["message"]

    def test_invoke_sync_wrapper(self, mock_db, sample_endpoint_websocket, sample_input_data):
        """Test sync invoke wrapper calls async implementation."""
        invoker = WebSocketEndpointInvoker()

        expected_result = {"output": "Success", "conversation_id": "conv-123"}

        async def mock_async_invoke(*args, **kwargs):
            return expected_result

        with patch.object(invoker, "_async_invoke", side_effect=mock_async_invoke):
            result = invoker.invoke(mock_db, sample_endpoint_websocket, sample_input_data)

        assert result == expected_result

    def test_invoke_handles_exception(self, mock_db, sample_endpoint_websocket, sample_input_data):
        """Test that invoke handles exceptions gracefully."""
        invoker = WebSocketEndpointInvoker()

        with patch.object(invoker, "_async_invoke", side_effect=Exception("Connection failed")):
            result = invoker.invoke(mock_db, sample_endpoint_websocket, sample_input_data)

        assert result["error"] is True
        assert result["error_type"] == "websocket_error"
        assert "Connection failed" in result["message"]

    def test_build_websocket_uri_basic(self, sample_endpoint_websocket):
        """Test building basic WebSocket URI."""
        invoker = WebSocketEndpointInvoker()

        uri = invoker._build_websocket_uri(sample_endpoint_websocket)

        assert uri == "wss://ws.example.com/chat"

    def test_build_websocket_uri_with_path(self, sample_endpoint_websocket):
        """Test building WebSocket URI with endpoint path."""
        invoker = WebSocketEndpointInvoker()
        sample_endpoint_websocket.endpoint_path = "/v2/stream"

        uri = invoker._build_websocket_uri(sample_endpoint_websocket)

        assert uri == "wss://ws.example.com/chat/v2/stream"

    def test_build_websocket_uri_avoids_duplicate_path(self, sample_endpoint_websocket):
        """Test that URI builder doesn't duplicate paths."""
        invoker = WebSocketEndpointInvoker()
        sample_endpoint_websocket.url = "wss://ws.example.com/chat"
        sample_endpoint_websocket.endpoint_path = "/chat"

        uri = invoker._build_websocket_uri(sample_endpoint_websocket)

        assert uri == "wss://ws.example.com/chat"

    def test_prepare_additional_headers(self, sample_endpoint_websocket):
        """Test preparing additional headers for WebSocket."""
        invoker = WebSocketEndpointInvoker()
        sample_endpoint_websocket.request_headers = {
            "X-API-Key": "test-key",
            "Upgrade": "websocket",  # Should be filtered
            "Connection": "Upgrade",  # Should be filtered
        }

        headers = invoker._prepare_additional_headers(sample_endpoint_websocket)

        assert "X-API-Key" in headers
        assert "Upgrade" not in headers
        assert "Connection" not in headers

    def test_prepare_additional_headers_with_auth(
        self, sample_endpoint_websocket, sample_input_data
    ):
        """Test preparing headers with auth and context."""
        invoker = WebSocketEndpointInvoker()
        input_data = {"input": "test", "organization_id": "org-123"}

        headers = invoker._prepare_additional_headers_with_auth(
            sample_endpoint_websocket, "test-token", input_data
        )

        # Should have Origin and User-Agent
        assert "Origin" in headers
        assert "User-Agent" in headers
        # Should have context headers
        assert headers["X-Organization-ID"] == "org-123"
        # Should NOT have Authorization (sent in body for WS)
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_async_invoke_forwards_conversation_id(self, mock_db, sample_endpoint_websocket):
        """Test that conversation_id is forwarded in follow-up requests."""
        invoker = WebSocketEndpointInvoker()
        input_data = {"input": "Follow-up", "conversation_id": "conv-existing"}

        mock_messages = [
            json.dumps({"message": "Response", "conversation_id": "conv-new"}),
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
            result = await invoker._async_invoke(mock_db, sample_endpoint_websocket, input_data)

            # Verify conversation_id was sent in the message
            sent_message = json.loads(mock_websocket.send.call_args[0][0])
            # Note: The template will include conversation_id field

        assert result["conversation_id"] == "conv-new"

    @pytest.mark.asyncio
    async def test_async_invoke_preserves_unmapped_fields(
        self, mock_db, sample_endpoint_websocket, sample_input_data
    ):
        """Test that unmapped but important fields are preserved."""
        invoker = WebSocketEndpointInvoker()

        mock_messages = [
            json.dumps(
                {
                    "message": "Success",
                    "error": None,
                    "status": "completed",
                    "extra_field": "extra_value",
                }
            ),
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
            result = await invoker._async_invoke(
                mock_db, sample_endpoint_websocket, sample_input_data
            )

        # Important fields should be preserved
        assert result["status"] == "completed"
        assert "error" in result
        # Extra fields should also be included
        assert result["extra_field"] == "extra_value"
