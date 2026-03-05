"""
Tests for connection manager in rhesis.backend.app.services.connector.manager

This module tests the ConnectionManager class including:
- WebSocket connection lifecycle
- Function registry management
- Test request sending
- Connection status queries
- Message routing and handling
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.connector.manager import ConnectionManager
from rhesis.backend.app.services.connector.schemas import (
    ConnectionStatus,
    FunctionMetadata,
    WebSocketConnectionContext,
)


class TestConnectionManager:
    """Test ConnectionManager class functionality"""

    @pytest.fixture
    def manager(self):
        """Create a fresh manager instance for each test."""
        return ConnectionManager()

    def test_get_connection_key(self, manager: ConnectionManager):
        """Test connection key generation"""
        key = manager.get_connection_key("project-123", "staging")
        assert key == "project-123:staging"

    @pytest.mark.asyncio
    async def test_connect(
        self,
        manager: ConnectionManager,
        mock_websocket,
        connection_context: WebSocketConnectionContext,
    ):
        """Test WebSocket connection registration"""
        with patch.object(manager, "_track_background_task", return_value=Mock()):
            await manager.connect(
                connection_context.connection_id,
                connection_context,
                mock_websocket,
            )

        conn_id = connection_context.connection_id
        assert conn_id in manager._connections
        assert manager._connections[conn_id] == mock_websocket
        assert conn_id in manager._contexts
        assert manager._contexts[conn_id] == connection_context
        assert conn_id in manager._connection_projects
        assert manager._connection_projects[conn_id] == set()

    def test_disconnect(
        self,
        manager: ConnectionManager,
        mock_websocket,
        connection_context: WebSocketConnectionContext,
    ):
        """Test WebSocket disconnection"""
        conn_id = connection_context.connection_id
        key = manager.get_connection_key("project-123", "development")
        manager._connections[conn_id] = mock_websocket
        manager._contexts[conn_id] = connection_context
        manager._connection_projects[conn_id] = {key}
        manager._project_routing[key] = conn_id
        manager._registries[key] = []

        manager.disconnect_by_connection_id(conn_id)

        assert conn_id not in manager._connections
        assert conn_id not in manager._contexts
        assert conn_id not in manager._connection_projects
        assert key not in manager._project_routing
        assert key not in manager._registries

    def test_disconnect_nonexistent(self, manager: ConnectionManager):
        """Test disconnecting a non-existent connection"""
        manager.disconnect_by_connection_id("nonexistent-conn")

    def test_register_functions(self, manager: ConnectionManager):
        """Test function registration"""
        functions = [
            FunctionMetadata(
                name="test_func",
                parameters={"param1": {"type": "string"}},
                return_type="string",
                metadata={},
            )
        ]

        manager.register_functions("project-123", "development", functions)

        key = manager.get_connection_key("project-123", "development")
        assert key in manager._registries
        assert manager._registries[key] == functions

    @pytest.mark.asyncio
    async def test_send_test_request_success(self, manager: ConnectionManager, mock_websocket):
        """Test successful test request sending"""
        conn_id = "conn-test-123"
        key = manager.get_connection_key("project-123", "development")
        manager._connections[conn_id] = mock_websocket
        manager._project_routing[key] = conn_id

        result = await manager.send_test_request(
            project_id="project-123",
            environment="development",
            test_run_id="test_abc123",
            function_name="test_func",
            inputs={"param": "value"},
        )

        assert result is True
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "execute_test"
        assert call_args["test_run_id"] == "test_abc123"
        assert call_args["function_name"] == "test_func"
        assert call_args["inputs"] == {"param": "value"}

    @pytest.mark.asyncio
    async def test_send_test_request_not_connected(self, manager: ConnectionManager):
        """Test test request sending when not connected"""
        result = await manager.send_test_request(
            project_id="nonexistent",
            environment="development",
            test_run_id="test_abc123",
            function_name="test_func",
            inputs={},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_test_request_send_error(self, manager: ConnectionManager, mock_websocket):
        """Test test request sending when send_json fails"""
        mock_websocket.send_json.side_effect = Exception("Connection error")
        conn_id = "conn-test-123"
        key = manager.get_connection_key("project-123", "development")
        manager._connections[conn_id] = mock_websocket
        manager._project_routing[key] = conn_id

        result = await manager.send_test_request(
            project_id="project-123",
            environment="development",
            test_run_id="test_abc123",
            function_name="test_func",
            inputs={},
        )

        assert result is False

    def test_get_connection_status_connected(self, manager: ConnectionManager, mock_websocket):
        """Test getting status for connected project"""
        conn_id = "conn-test-123"
        key = manager.get_connection_key("project-123", "development")
        manager._connections[conn_id] = mock_websocket
        manager._project_routing[key] = conn_id
        functions = [
            FunctionMetadata(
                name="test_func",
                parameters={"param1": {"type": "string"}},
                return_type="string",
                metadata={},
            )
        ]
        manager._registries[key] = functions

        status = manager.get_connection_status("project-123", "development")

        assert isinstance(status, ConnectionStatus)
        assert status.project_id == "project-123"
        assert status.environment == "development"
        assert status.connected is True
        assert len(status.functions) == 1
        assert status.functions[0].name == "test_func"

    def test_get_connection_status_not_connected(self, manager: ConnectionManager):
        """Test getting status for disconnected project"""
        status = manager.get_connection_status("nonexistent", "development")

        assert isinstance(status, ConnectionStatus)
        assert status.project_id == "nonexistent"
        assert status.environment == "development"
        assert status.connected is False
        assert len(status.functions) == 0

    @pytest.mark.asyncio
    async def test_is_connected_true(self, manager: ConnectionManager, mock_websocket):
        """Test is_connected returns True for connected project"""
        conn_id = "conn-test-123"
        key = manager.get_connection_key("project-123", "development")
        manager._project_routing[key] = conn_id
        manager._connections[conn_id] = mock_websocket

        assert await manager.is_connected("project-123", "development") is True

    @pytest.mark.asyncio
    async def test_is_connected_false(self, manager: ConnectionManager):
        """Test is_connected returns False for non-connected project"""
        assert await manager.is_connected("nonexistent", "development") is False

    @pytest.mark.asyncio
    async def test_handle_registration(self, manager: ConnectionManager, sample_register_message):
        """Test registration message handling"""
        await manager.handle_registration("project-123", "development", sample_register_message)

        key = manager.get_connection_key("project-123", "development")
        assert key in manager._registries
        assert len(manager._registries[key]) == 2
        assert manager._registries[key][0].name == "get_weather"
        assert manager._registries[key][1].name == "calculate_sum"

    @pytest.mark.asyncio
    async def test_handle_registration_invalid(self, manager: ConnectionManager):
        """Test registration with invalid message"""
        invalid_message = {"type": "register", "invalid": "data"}

        await manager.handle_registration("project-123", "development", invalid_message)

        key = manager.get_connection_key("project-123", "development")
        assert key not in manager._registries

    @pytest.mark.asyncio
    async def test_handle_message_register(
        self,
        manager: ConnectionManager,
        test_db: Session,
        sample_register_message,
        project_context,
    ):
        """Test handling register message"""
        conn_id = "conn-test-123"
        context = WebSocketConnectionContext(
            connection_id=conn_id,
            user_id=project_context["user_id"],
            organization_id=project_context["organization_id"],
        )
        manager._contexts[conn_id] = context
        manager._connection_projects[conn_id] = set()

        sample_register_message["project_id"] = project_context["project_id"]
        sample_register_message["environment"] = project_context["environment"]

        with (
            patch("rhesis.backend.app.services.connector.manager.message_handler") as mock_handler,
            patch.object(
                manager,
                "_authorize_and_register",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            mock_handler.handle_register_message = AsyncMock(
                return_value={"type": "registered", "status": "success"}
            )

            response = await manager.handle_message(
                connection_id=conn_id,
                message=sample_register_message,
                db=test_db,
                organization_id=project_context["organization_id"],
                user_id=project_context["user_id"],
            )

            assert response["type"] == "registered"
            assert response["status"] == "success"

            key = manager.get_connection_key(
                project_context["project_id"],
                project_context["environment"],
            )
            assert key in manager._registries

    @pytest.mark.asyncio
    async def test_handle_message_test_result(
        self,
        manager: ConnectionManager,
        sample_test_result_message,
        project_context,
    ):
        """Test handling test_result message"""
        conn_id = "conn-test-123"
        key = manager.get_connection_key(
            project_context["project_id"], project_context["environment"]
        )
        manager._connection_projects[conn_id] = {key}

        with patch("rhesis.backend.app.services.connector.manager.message_handler") as mock_handler:
            mock_handler.handle_test_result_message = AsyncMock()

            response = await manager.handle_message(
                connection_id=conn_id,
                message=sample_test_result_message,
                db=None,
                organization_id=None,
            )

            assert response is None
            mock_handler.handle_test_result_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_pong(
        self,
        manager: ConnectionManager,
        sample_pong_message,
        project_context,
    ):
        """Test handling pong message"""
        conn_id = "conn-test-123"
        key = manager.get_connection_key(
            project_context["project_id"], project_context["environment"]
        )
        manager._connection_projects[conn_id] = {key}

        with patch("rhesis.backend.app.services.connector.manager.message_handler") as mock_handler:
            mock_handler.handle_pong_message = AsyncMock()

            response = await manager.handle_message(
                connection_id=conn_id,
                message=sample_pong_message,
                db=None,
                organization_id=None,
            )

            assert response is None
            mock_handler.handle_pong_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_unknown(self, manager: ConnectionManager, project_context):
        """Test handling unknown message type"""
        conn_id = "conn-test-123"
        unknown_message = {"type": "unknown_type", "data": "something"}

        response = await manager.handle_message(
            connection_id=conn_id,
            message=unknown_message,
            db=None,
            organization_id=None,
        )

        assert response is None

    @pytest.mark.asyncio
    async def test_multiple_connections_different_environments(self, manager: ConnectionManager):
        """Test managing multiple connections for same project in different environments"""
        ws_dev = Mock()
        ws_prod = Mock()

        conn_id_dev = "conn-dev"
        conn_id_prod = "conn-prod"

        manager._connections[conn_id_dev] = ws_dev
        manager._connections[conn_id_prod] = ws_prod

        key_dev = manager.get_connection_key("project-123", "development")
        key_prod = manager.get_connection_key("project-123", "production")
        manager._project_routing[key_dev] = conn_id_dev
        manager._project_routing[key_prod] = conn_id_prod

        assert await manager.is_connected("project-123", "development")
        assert await manager.is_connected("project-123", "production")

        assert manager._connections[conn_id_dev] == ws_dev
        assert manager._connections[conn_id_prod] == ws_prod

    @pytest.mark.asyncio
    async def test_reconnection_replaces_old_connection(self, manager: ConnectionManager):
        """Test that reconnecting with the same connection_id replaces the old WebSocket"""
        ws_old = Mock()
        ws_new = Mock()

        conn_id = "conn-test-123"
        context = WebSocketConnectionContext(
            connection_id=conn_id,
            user_id="user-1",
            organization_id="org-1",
        )

        with patch.object(manager, "_track_background_task", return_value=Mock()):
            await manager.connect(conn_id, context, ws_old)
            assert manager._connections[conn_id] == ws_old

            await manager.connect(conn_id, context, ws_new)
            assert manager._connections[conn_id] == ws_new
