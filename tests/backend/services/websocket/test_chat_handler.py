"""Tests for chat message handler."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rhesis.backend.app.schemas.websocket import (
    ConnectionTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.services.invokers.common.schemas import ErrorResponse
from rhesis.backend.app.services.websocket.handlers.chat import (
    handle_chat_message,
    _send_chat_error,
)


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock()
    user.id = uuid4()
    user.organization_id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_manager():
    """Create a mock WebSocketManager."""
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    return manager


class TestChatMessageHandler:
    """Tests for handle_chat_message function."""

    @pytest.mark.asyncio
    async def test_missing_endpoint_id(self, mock_manager, mock_user):
        """Test that missing endpoint_id returns error."""
        message = WebSocketMessage(
            type=EventType.CHAT_MESSAGE,
            correlation_id="corr-123",
            payload={"message": "Hello"},
        )

        await handle_chat_message(mock_manager, "conn-1", mock_user, message)

        # Should broadcast error
        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]
        assert msg.type == EventType.CHAT_ERROR
        assert "endpoint_id" in msg.payload["error"]

    @pytest.mark.asyncio
    async def test_missing_message(self, mock_manager, mock_user):
        """Test that missing message returns error."""
        message = WebSocketMessage(
            type=EventType.CHAT_MESSAGE,
            correlation_id="corr-123",
            payload={"endpoint_id": str(uuid4())},
        )

        await handle_chat_message(mock_manager, "conn-1", mock_user, message)

        # Should broadcast error
        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]
        assert msg.type == EventType.CHAT_ERROR
        assert "message" in msg.payload["error"]

    @pytest.mark.asyncio
    async def test_empty_payload(self, mock_manager, mock_user):
        """Test that empty payload returns error."""
        message = WebSocketMessage(
            type=EventType.CHAT_MESSAGE,
            correlation_id="corr-123",
            payload={},
        )

        await handle_chat_message(mock_manager, "conn-1", mock_user, message)

        # Should broadcast error for missing endpoint_id
        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]
        assert msg.type == EventType.CHAT_ERROR

    @pytest.mark.asyncio
    async def test_none_payload(self, mock_manager, mock_user):
        """Test that None payload returns error."""
        message = WebSocketMessage(
            type=EventType.CHAT_MESSAGE,
            correlation_id="corr-123",
            payload=None,
        )

        await handle_chat_message(mock_manager, "conn-1", mock_user, message)

        # Should broadcast error for missing endpoint_id
        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]
        assert msg.type == EventType.CHAT_ERROR

    @pytest.mark.asyncio
    async def test_successful_invocation(self, mock_manager, mock_user):
        """Test successful endpoint invocation."""
        endpoint_id = str(uuid4())
        message = WebSocketMessage(
            type=EventType.CHAT_MESSAGE,
            correlation_id="corr-123",
            payload={
                "endpoint_id": endpoint_id,
                "message": "Hello, world!",
            },
        )

        # Mock the endpoint service
        mock_result = {
            "output": "Hello! How can I help you?",
            "trace_id": str(uuid4()),
        }

        with patch(
            "rhesis.backend.app.services.websocket.handlers.chat.EndpointService"
        ) as MockEndpointService:
            mock_service = MockEndpointService.return_value
            mock_service.invoke_endpoint = AsyncMock(return_value=mock_result)

            with patch(
                "rhesis.backend.app.services.websocket.handlers.chat.get_db"
            ) as mock_get_db:
                # Mock the context manager
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

                await handle_chat_message(mock_manager, "conn-1", mock_user, message)

        # Should broadcast response
        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]
        target = call_args[0][1]

        assert msg.type == EventType.CHAT_RESPONSE
        assert msg.correlation_id == "corr-123"
        assert msg.payload["output"] == mock_result["output"]
        assert msg.payload["trace_id"] == mock_result["trace_id"]
        assert msg.payload["endpoint_id"] == endpoint_id
        assert isinstance(target, ConnectionTarget)
        assert target.connection_id == "conn-1"

    @pytest.mark.asyncio
    async def test_invocation_error(self, mock_manager, mock_user):
        """Test endpoint invocation error handling."""
        endpoint_id = str(uuid4())
        message = WebSocketMessage(
            type=EventType.CHAT_MESSAGE,
            correlation_id="corr-123",
            payload={
                "endpoint_id": endpoint_id,
                "message": "Hello, world!",
            },
        )

        with patch(
            "rhesis.backend.app.services.websocket.handlers.chat.EndpointService"
        ) as MockEndpointService:
            mock_service = MockEndpointService.return_value
            mock_service.invoke_endpoint = AsyncMock(
                side_effect=Exception("Endpoint not found")
            )

            with patch(
                "rhesis.backend.app.services.websocket.handlers.chat.get_db"
            ) as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

                await handle_chat_message(mock_manager, "conn-1", mock_user, message)

        # Should broadcast error
        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]

        assert msg.type == EventType.CHAT_ERROR
        assert msg.correlation_id == "corr-123"
        assert "Endpoint not found" in msg.payload["error"]
        assert msg.payload["error_type"] == "Exception"

    @pytest.mark.asyncio
    async def test_error_response_from_endpoint(self, mock_manager, mock_user):
        """Test handling ErrorResponse from endpoint invocation."""
        endpoint_id = str(uuid4())
        message = WebSocketMessage(
            type=EventType.CHAT_MESSAGE,
            correlation_id="corr-123",
            payload={
                "endpoint_id": endpoint_id,
                "message": "Hello, world!",
            },
        )

        # Create an ErrorResponse object (simulating what the endpoint returns on error)
        error_response = ErrorResponse(
            output="HTTP 500 error: Internal Server Error",
            error=True,
            error_type="http_error",
            message="The endpoint returned an error",
            status_code=500,
        )

        with patch(
            "rhesis.backend.app.services.websocket.handlers.chat.EndpointService"
        ) as MockEndpointService:
            mock_service = MockEndpointService.return_value
            mock_service.invoke_endpoint = AsyncMock(return_value=error_response)

            with patch(
                "rhesis.backend.app.services.websocket.handlers.chat.get_db"
            ) as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

                await handle_chat_message(mock_manager, "conn-1", mock_user, message)

        # Should broadcast error with the ErrorResponse details
        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]

        assert msg.type == EventType.CHAT_ERROR
        assert msg.correlation_id == "corr-123"
        assert msg.payload["error"] == "HTTP 500 error: Internal Server Error"
        assert msg.payload["error_type"] == "http_error"

    @pytest.mark.asyncio
    async def test_conversation_id_from_response(self, mock_manager, mock_user):
        """Test that conversation_id from endpoint response is returned."""
        endpoint_id = str(uuid4())
        response_conversation_id = str(uuid4())
        message = WebSocketMessage(
            type=EventType.CHAT_MESSAGE,
            correlation_id="corr-123",
            payload={
                "endpoint_id": endpoint_id,
                "message": "Hello, world!",
            },
        )

        # Mock the endpoint service to return a conversation_id
        mock_result = {
            "output": "Hello! How can I help you?",
            "trace_id": str(uuid4()),
            "conversation_id": response_conversation_id,
        }

        with patch(
            "rhesis.backend.app.services.websocket.handlers.chat.EndpointService"
        ) as MockEndpointService:
            mock_service = MockEndpointService.return_value
            mock_service.invoke_endpoint = AsyncMock(return_value=mock_result)

            with patch(
                "rhesis.backend.app.services.websocket.handlers.chat.get_db"
            ) as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

                await handle_chat_message(mock_manager, "conn-1", mock_user, message)

        # Should include conversation_id in response
        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]

        assert msg.type == EventType.CHAT_RESPONSE
        assert msg.payload["conversation_id"] == response_conversation_id

    @pytest.mark.asyncio
    async def test_conversation_id_echoed_back(self, mock_manager, mock_user):
        """Test that input conversation_id is echoed back if no new one from response."""
        endpoint_id = str(uuid4())
        input_conversation_id = str(uuid4())
        message = WebSocketMessage(
            type=EventType.CHAT_MESSAGE,
            correlation_id="corr-123",
            payload={
                "endpoint_id": endpoint_id,
                "message": "Continue our conversation",
                "conversation_id": input_conversation_id,
            },
        )

        # Mock result without conversation_id
        mock_result = {
            "output": "Sure, I remember our chat!",
            "trace_id": str(uuid4()),
        }

        with patch(
            "rhesis.backend.app.services.websocket.handlers.chat.EndpointService"
        ) as MockEndpointService:
            mock_service = MockEndpointService.return_value
            mock_service.invoke_endpoint = AsyncMock(return_value=mock_result)

            with patch(
                "rhesis.backend.app.services.websocket.handlers.chat.get_db"
            ) as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

                await handle_chat_message(mock_manager, "conn-1", mock_user, message)

        # Should echo back input conversation_id
        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]

        assert msg.type == EventType.CHAT_RESPONSE
        assert msg.payload["conversation_id"] == input_conversation_id

    @pytest.mark.asyncio
    async def test_correlation_id_preserved(self, mock_manager, mock_user):
        """Test that correlation_id is preserved in response."""
        correlation_id = "test-correlation-id-123"
        message = WebSocketMessage(
            type=EventType.CHAT_MESSAGE,
            correlation_id=correlation_id,
            payload={
                "endpoint_id": str(uuid4()),
                "message": "Test message",
            },
        )

        mock_result = {"output": "Response", "trace_id": str(uuid4())}

        with patch(
            "rhesis.backend.app.services.websocket.handlers.chat.EndpointService"
        ) as MockEndpointService:
            mock_service = MockEndpointService.return_value
            mock_service.invoke_endpoint = AsyncMock(return_value=mock_result)

            with patch(
                "rhesis.backend.app.services.websocket.handlers.chat.get_db"
            ) as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

                await handle_chat_message(mock_manager, "conn-1", mock_user, message)

        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]
        assert msg.correlation_id == correlation_id


class TestSendChatError:
    """Tests for _send_chat_error helper function."""

    @pytest.mark.asyncio
    async def test_sends_error_message(self, mock_manager):
        """Test that error message is sent correctly."""
        await _send_chat_error(
            mock_manager,
            "conn-1",
            "corr-123",
            "Test error message",
            "TestErrorType",
        )

        mock_manager.broadcast.assert_called_once()
        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]
        target = call_args[0][1]

        assert msg.type == EventType.CHAT_ERROR
        assert msg.correlation_id == "corr-123"
        assert msg.payload["error"] == "Test error message"
        assert msg.payload["error_type"] == "TestErrorType"
        assert isinstance(target, ConnectionTarget)
        assert target.connection_id == "conn-1"

    @pytest.mark.asyncio
    async def test_default_error_type(self, mock_manager):
        """Test default error type."""
        await _send_chat_error(
            mock_manager,
            "conn-1",
            None,
            "Test error",
        )

        call_args = mock_manager.broadcast.call_args
        msg = call_args[0][0]
        assert msg.payload["error_type"] == "Error"
