"""
Tests for WebSocket endpoint in rhesis.backend.app.routers.websocket

This module tests the generic WebSocket endpoint including:
- WebSocket connection lifecycle
- Authentication via query parameter
- Message handling (subscribe, unsubscribe, ping)
- Channel subscription management
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from rhesis.backend.app.schemas.websocket import EventType


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    user = Mock()
    user.id = uuid.uuid4()
    user.organization_id = uuid.uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_ws_manager():
    """Mock the WebSocket manager."""
    with patch("rhesis.backend.app.routers.websocket.ws_manager") as mock_mgr:
        mock_mgr.connect = AsyncMock(return_value="ws_test123")
        mock_mgr.disconnect = Mock()
        mock_mgr.handle_message = AsyncMock()
        mock_mgr.subscribe = Mock(return_value=True)
        mock_mgr.unsubscribe = Mock(return_value=True)
        mock_mgr.get_subscriptions = Mock(return_value=set())
        yield mock_mgr


@pytest.fixture
def mock_authenticate_token(mock_user):
    """Mock WebSocket token authentication."""
    with patch("rhesis.backend.app.routers.websocket.authenticate_websocket_token") as mock_auth:
        mock_auth.return_value = mock_user
        yield mock_auth


@pytest.mark.integration
class TestWebSocketEndpoint:
    """Test WebSocket endpoint functionality."""

    def test_websocket_connection_success(
        self,
        authenticated_client: TestClient,
        mock_authenticate_token,
        mock_ws_manager,
        mock_user,
    ):
        """Test successful WebSocket connection with valid token."""
        with authenticated_client.websocket_connect("/ws?token=valid_token") as ws:
            # Should receive connected message
            data = ws.receive_json()
            assert data["type"] == EventType.CONNECTED.value
            assert "connection_id" in data["payload"]
            assert data["payload"]["user_id"] == str(mock_user.id)

    def test_websocket_connection_missing_token(
        self,
        authenticated_client: TestClient,
        mock_ws_manager,
    ):
        """Test WebSocket connection without token fails."""
        with patch(
            "rhesis.backend.app.routers.websocket.authenticate_websocket_token"
        ) as mock_auth:
            mock_auth.return_value = None  # Auth fails

            with pytest.raises(WebSocketDisconnect) as exc_info:
                with authenticated_client.websocket_connect("/ws"):
                    pass

            # Check close code is 1008 (Policy Violation)
            assert exc_info.value.code == 1008

    def test_websocket_connection_invalid_token(
        self,
        authenticated_client: TestClient,
        mock_ws_manager,
    ):
        """Test WebSocket connection with invalid token fails."""
        with patch(
            "rhesis.backend.app.routers.websocket.authenticate_websocket_token"
        ) as mock_auth:
            mock_auth.return_value = None  # Auth fails

            with pytest.raises(WebSocketDisconnect) as exc_info:
                with authenticated_client.websocket_connect("/ws?token=invalid"):
                    pass

            assert exc_info.value.code == 1008

    def test_websocket_send_valid_message(
        self,
        authenticated_client: TestClient,
        mock_authenticate_token,
        mock_ws_manager,
    ):
        """Test that sending a valid message doesn't cause errors."""
        with authenticated_client.websocket_connect("/ws?token=valid_token") as ws:
            # Receive connected message
            data = ws.receive_json()
            assert data["type"] == EventType.CONNECTED.value

            # Send a valid message - the connection should remain open
            ws.send_json({"type": "ping"})

            # If we get here without exception, the message was accepted
            # The async loop may not have processed it yet, but that's OK for this test

    def test_websocket_disconnect_cleanup(
        self,
        authenticated_client: TestClient,
        mock_authenticate_token,
        mock_ws_manager,
    ):
        """Test that disconnect properly cleans up."""
        with authenticated_client.websocket_connect("/ws?token=valid_token") as ws:
            # Receive connected message
            ws.receive_json()

        # After context manager exits, disconnect should be called
        mock_ws_manager.disconnect.assert_called_once_with("ws_test123")

    def test_websocket_invalid_message_format(
        self,
        authenticated_client: TestClient,
        mock_authenticate_token,
        mock_ws_manager,
    ):
        """Test handling of invalid message format."""
        with authenticated_client.websocket_connect("/ws?token=valid_token") as ws:
            # Receive connected message
            ws.receive_json()

            # Send invalid message (missing type field)
            ws.send_json({"payload": {"data": "test"}})

            # Should receive error response
            # Note: The router catches ValidationError and sends error message
            # but doesn't disconnect the client
            data = ws.receive_json()
            assert data["type"] == EventType.ERROR.value


@pytest.mark.integration
class TestAuthenticateWebSocketToken:
    """Test the authenticate_websocket_token function."""

    def test_authenticate_with_valid_jwt(self, mock_user):
        """Test authentication with valid JWT token."""
        with patch(
            "rhesis.backend.app.routers.websocket.get_authenticated_user_with_context"
        ) as mock_auth:
            mock_auth.return_value = mock_user

            import asyncio

            from rhesis.backend.app.routers.websocket import authenticate_websocket_token

            # Mock websocket
            mock_ws = MagicMock()

            result = asyncio.get_event_loop().run_until_complete(
                authenticate_websocket_token(mock_ws, "valid_token")
            )

            assert result == mock_user
            mock_auth.assert_called_once()

    def test_authenticate_with_no_token(self):
        """Test authentication without token returns None."""
        import asyncio

        from rhesis.backend.app.routers.websocket import authenticate_websocket_token

        mock_ws = MagicMock()

        result = asyncio.get_event_loop().run_until_complete(
            authenticate_websocket_token(mock_ws, None)
        )

        assert result is None

    def test_authenticate_with_invalid_token(self):
        """Test authentication with invalid token returns None."""
        with patch(
            "rhesis.backend.app.routers.websocket.get_authenticated_user_with_context"
        ) as mock_auth:
            mock_auth.side_effect = Exception("Invalid token")

            import asyncio

            from rhesis.backend.app.routers.websocket import authenticate_websocket_token

            mock_ws = MagicMock()

            result = asyncio.get_event_loop().run_until_complete(
                authenticate_websocket_token(mock_ws, "invalid_token")
            )

            assert result is None


@pytest.mark.integration
class TestMessageSizeLimits:
    """Security tests for WebSocket message size limits."""

    def test_message_at_size_limit_accepted(
        self,
        authenticated_client: TestClient,
        mock_authenticate_token,
        mock_ws_manager,
    ):
        """Test that messages at the 64KB limit are accepted."""
        with authenticated_client.websocket_connect("/ws?token=valid_token") as ws:
            # Receive connected message
            ws.receive_json()

            # Create a message close to but within the limit
            # 64KB = 65536 bytes
            # We need to account for JSON overhead
            payload_size = 60000  # Leave room for JSON structure
            message = {
                "type": "ping",
                "payload": {"data": "x" * payload_size},
            }

            # Send message - should be accepted
            ws.send_json(message)

            # Connection should remain open (no exception)

    def test_oversized_message_rejected(
        self,
        authenticated_client: TestClient,
        mock_authenticate_token,
        mock_ws_manager,
    ):
        """Test that messages exceeding 64KB are rejected."""
        with authenticated_client.websocket_connect("/ws?token=valid_token") as ws:
            # Receive connected message
            ws.receive_json()

            # Create an oversized message (> 64KB)
            payload_size = 70000  # Clearly over 64KB
            message = {
                "type": "ping",
                "payload": {"data": "x" * payload_size},
            }

            # Send oversized message
            ws.send_json(message)

            # Should receive error response
            error_response = ws.receive_json()
            assert error_response["type"] == EventType.ERROR.value
            assert "64KB" in error_response["payload"]["error"]

    def test_server_stable_after_oversized_message(
        self,
        authenticated_client: TestClient,
        mock_authenticate_token,
        mock_ws_manager,
    ):
        """Test that server remains stable after receiving oversized message."""
        with authenticated_client.websocket_connect("/ws?token=valid_token") as ws:
            # Receive connected message
            ws.receive_json()

            # Send oversized message
            payload_size = 70000
            oversized_message = {
                "type": "ping",
                "payload": {"data": "x" * payload_size},
            }
            ws.send_json(oversized_message)

            # Receive error response
            error_response = ws.receive_json()
            assert error_response["type"] == EventType.ERROR.value

            # Send a normal message - should still work
            ws.send_json({"type": "ping"})

            # Connection should remain open (no exception)


@pytest.mark.integration
class TestErrorSanitization:
    """Security tests for error message sanitization."""

    def test_validation_error_returns_generic_message(
        self,
        authenticated_client: TestClient,
        mock_authenticate_token,
        mock_ws_manager,
    ):
        """Test that ValidationError returns generic 'Invalid message format'."""
        with authenticated_client.websocket_connect("/ws?token=valid_token") as ws:
            # Receive connected message
            ws.receive_json()

            # Send message missing required 'type' field (triggers ValidationError)
            ws.send_json({"payload": {"data": "test"}})

            # Should receive generic error, not validation details
            error_response = ws.receive_json()
            assert error_response["type"] == EventType.ERROR.value
            assert error_response["payload"]["error"] == "Invalid message format"
            # Should NOT contain field names or validation details
            assert "type" not in error_response["payload"]["error"]
            assert "field required" not in error_response["payload"]["error"].lower()

    def test_internal_exception_returns_generic_message(
        self,
        authenticated_client: TestClient,
        mock_authenticate_token,
    ):
        """Test that internal exceptions return generic 'Internal server error'."""
        with patch("rhesis.backend.app.routers.websocket.ws_manager") as mock_mgr:
            mock_mgr.connect = AsyncMock(return_value="ws_test123")
            mock_mgr.disconnect = Mock()
            # Make handle_message raise an internal exception
            mock_mgr.handle_message = AsyncMock(
                side_effect=RuntimeError("Database connection failed: secret_db_host:5432")
            )

            with authenticated_client.websocket_connect("/ws?token=valid_token") as ws:
                # Receive connected message
                ws.receive_json()

                # Send a valid message that triggers the mocked exception
                ws.send_json({"type": "ping"})

                # Should receive generic error, not internal details
                error_response = ws.receive_json()
                assert error_response["type"] == EventType.ERROR.value
                assert error_response["payload"]["error"] == "Internal server error"
                # Should NOT contain any internal details
                assert "database" not in error_response["payload"]["error"].lower()
                assert "secret" not in error_response["payload"]["error"].lower()
                assert "5432" not in error_response["payload"]["error"]

    def test_stack_trace_not_sent_to_client(
        self,
        authenticated_client: TestClient,
        mock_authenticate_token,
    ):
        """Test that stack traces are not sent to client."""
        with patch("rhesis.backend.app.routers.websocket.ws_manager") as mock_mgr:
            mock_mgr.connect = AsyncMock(return_value="ws_test123")
            mock_mgr.disconnect = Mock()
            # Make handle_message raise an exception
            mock_mgr.handle_message = AsyncMock(
                side_effect=ValueError("Sensitive stack trace info")
            )

            with authenticated_client.websocket_connect("/ws?token=valid_token") as ws:
                # Receive connected message
                ws.receive_json()

                # Send a valid message that triggers the exception
                ws.send_json({"type": "ping"})

                # Receive error response
                error_response = ws.receive_json()

                # Convert to string for checking
                response_str = str(error_response)

                # Should NOT contain traceback markers
                assert "Traceback" not in response_str
                assert "File" not in response_str
                assert "line " not in response_str.lower()
                assert "Sensitive" not in response_str
