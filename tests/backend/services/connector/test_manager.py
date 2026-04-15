"""
Tests for connection manager in rhesis.backend.app.services.connector.manager

This module tests the ConnectionManager class including:
- WebSocket connection lifecycle
- Function registry management
- Test request sending
- Connection status queries
- Message routing and handling
"""

import asyncio
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
        manager._project_routing[key] = [conn_id]
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
        manager._project_routing[key] = [conn_id]

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
        """Test test request sending when send_json fails -- connection is evicted"""
        mock_websocket.send_json.side_effect = Exception("Connection error")
        conn_id = "conn-test-123"
        key = manager.get_connection_key("project-123", "development")
        manager._connections[conn_id] = mock_websocket
        manager._project_routing[key] = [conn_id]
        manager._connection_projects[conn_id] = {key}

        result = await manager.send_test_request(
            project_id="project-123",
            environment="development",
            test_run_id="test_abc123",
            function_name="test_func",
            inputs={},
        )

        assert result is False
        assert conn_id not in manager._project_routing.get(key, [])

    def test_get_connection_status_connected(self, manager: ConnectionManager, mock_websocket):
        """Test getting status for connected project"""
        conn_id = "conn-test-123"
        key = manager.get_connection_key("project-123", "development")
        manager._connections[conn_id] = mock_websocket
        manager._project_routing[key] = [conn_id]
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
        manager._project_routing[key] = [conn_id]
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
        manager._project_routing[key_dev] = [conn_id_dev]
        manager._project_routing[key_prod] = [conn_id_prod]

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


class TestConnectionPoolRouting:
    """Tests for multi-connection pool routing."""

    @pytest.fixture
    def manager(self):
        return ConnectionManager()

    def test_next_route_round_robins(self, manager):
        """Successive calls to _next_route cycle through the pool."""
        ws_a, ws_b, ws_c = Mock(), Mock(), Mock()
        manager._connections = {"a": ws_a, "b": ws_b, "c": ws_c}
        manager._project_routing["p:dev"] = ["a", "b", "c"]

        results = [manager._next_route("p", "dev") for _ in range(6)]
        assert results == ["a", "b", "c", "a", "b", "c"]

    def test_next_route_prunes_dead_connections(self, manager):
        """Dead connections are removed from pool on each call."""
        ws_b = Mock()
        manager._connections = {"b": ws_b}
        manager._project_routing["p:dev"] = ["a", "b", "c"]

        result = manager._next_route("p", "dev")
        assert result == "b"
        assert manager._project_routing["p:dev"] == ["b"]

    def test_next_route_returns_none_for_empty_pool(self, manager):
        """Returns None and cleans up when no live connections remain."""
        manager._connections = {}
        manager._project_routing["p:dev"] = ["a", "b"]
        manager._routing_counter["p:dev"] = 5

        result = manager._next_route("p", "dev")
        assert result is None
        assert "p:dev" not in manager._project_routing
        assert "p:dev" not in manager._routing_counter

    def test_next_route_returns_none_for_missing_key(self, manager):
        result = manager._next_route("unknown", "dev")
        assert result is None

    def test_remove_connection_route_removes_one(self, manager):
        """Removing one connection leaves the pool intact."""
        manager._project_routing["p:dev"] = ["a", "b", "c"]
        manager._registries["p:dev"] = []
        manager._metric_registries["p:dev"] = []

        manager._remove_connection_route("p:dev", "b")

        assert manager._project_routing["p:dev"] == ["a", "c"]
        assert "p:dev" in manager._registries

    def test_remove_connection_route_cleans_up_on_empty(self, manager):
        """Removing the last connection cleans up registries and counter."""
        manager._project_routing["p:dev"] = ["a"]
        manager._registries["p:dev"] = []
        manager._metric_registries["p:dev"] = []
        manager._routing_counter["p:dev"] = 3

        manager._remove_connection_route("p:dev", "a")

        assert "p:dev" not in manager._project_routing
        assert "p:dev" not in manager._registries
        assert "p:dev" not in manager._metric_registries
        assert "p:dev" not in manager._routing_counter

    def test_remove_connection_route_noop_for_missing(self, manager):
        """Removing a non-existent connection is a no-op."""
        manager._project_routing["p:dev"] = ["a"]
        manager._remove_connection_route("p:dev", "z")
        assert manager._project_routing["p:dev"] == ["a"]

    def test_remove_connection_route_cleans_connection_projects(self, manager):
        """Removing a route also removes the key from _connection_projects."""
        manager._project_routing["p:dev"] = ["a", "b"]
        manager._connection_projects["a"] = {"p:dev", "p:staging"}

        manager._remove_connection_route("p:dev", "a")

        assert manager._project_routing["p:dev"] == ["b"]
        assert "p:dev" not in manager._connection_projects["a"]
        assert "p:staging" in manager._connection_projects["a"]

    def test_remove_connection_route_handles_missing_connection_projects(self, manager):
        """No error if connection has no _connection_projects entry."""
        manager._project_routing["p:dev"] = ["a"]
        manager._remove_connection_route("p:dev", "a")
        assert "p:dev" not in manager._project_routing

    def test_disconnect_preserves_other_connections_route(self, manager):
        """Disconnecting one connection does not wipe the route for others."""
        ws_a, ws_b = Mock(), Mock()
        manager._connections = {"a": ws_a, "b": ws_b}
        key = manager.get_connection_key("proj", "dev")
        manager._project_routing[key] = ["a", "b"]
        manager._connection_projects["a"] = {key}
        manager._connection_projects["b"] = {key}
        manager._registries[key] = []

        manager.disconnect_by_connection_id("a")

        assert manager._project_routing[key] == ["b"]
        assert key in manager._registries

    def test_has_local_route_with_pool(self, manager):
        ws = Mock()
        manager._connections = {"b": ws}
        key = manager.get_connection_key("proj", "dev")
        manager._project_routing[key] = ["a", "b"]

        assert manager.has_local_route("proj", "dev") is True

    def test_has_local_route_false_when_all_dead(self, manager):
        manager._connections = {}
        key = manager.get_connection_key("proj", "dev")
        manager._project_routing[key] = ["a", "b"]

        assert manager.has_local_route("proj", "dev") is False

    def test_get_connection_status_false_when_pool_has_dead_conns(self, manager):
        """get_connection_status reports disconnected when pool entries are stale."""
        key = manager.get_connection_key("proj", "dev")
        manager._project_routing[key] = ["dead-conn"]

        status = manager.get_connection_status("proj", "dev")
        assert status.connected is False

    @pytest.mark.asyncio
    async def test_is_connected_false_when_pool_has_dead_conns(self, manager):
        """is_connected returns False when pool entries are stale."""
        key = manager.get_connection_key("proj", "dev")
        manager._project_routing[key] = ["dead-conn"]

        assert await manager.is_connected("proj", "dev") is False

    def test_routing_counter_wraps_around(self, manager):
        """Counter stays bounded via modulo."""
        ws = Mock()
        manager._connections = {"a": ws, "b": ws}
        manager._project_routing["p:dev"] = ["a", "b"]
        manager._routing_counter["p:dev"] = 0

        for _ in range(10):
            manager._next_route("p", "dev")

        assert manager._routing_counter["p:dev"] < 2


class TestHeartbeatPing:
    """Tests for application-level ping in the heartbeat loop."""

    @pytest.fixture
    def manager(self):
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_heartbeat_sends_ping_after_interval(self, manager, mock_websocket):
        """Heartbeat sends {"type": "ping"} after _PING_INTERVAL_TICKS ticks."""
        conn_id = "conn-ping-test"
        manager._connections[conn_id] = mock_websocket

        # Set interval to 2 ticks so the test is fast
        manager._PING_INTERVAL_TICKS = 2

        tick_count = 0
        original_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            nonlocal tick_count
            tick_count += 1
            # Let it run for 3 ticks then remove the connection to stop the loop
            if tick_count >= 3:
                manager._connections.pop(conn_id, None)
            await original_sleep(0)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await manager._heartbeat_loop(conn_id)

        ping_calls = [
            call
            for call in mock_websocket.send_json.call_args_list
            if call[0][0] == {"type": "ping"}
        ]
        assert len(ping_calls) == 1

    @pytest.mark.asyncio
    async def test_heartbeat_does_not_ping_before_interval(self, manager, mock_websocket):
        """No ping is sent before _PING_INTERVAL_TICKS ticks elapse."""
        conn_id = "conn-no-ping"
        manager._connections[conn_id] = mock_websocket
        manager._PING_INTERVAL_TICKS = 10

        tick_count = 0
        original_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 3:
                manager._connections.pop(conn_id, None)
            await original_sleep(0)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await manager._heartbeat_loop(conn_id)

        ping_calls = [
            call
            for call in mock_websocket.send_json.call_args_list
            if call[0][0] == {"type": "ping"}
        ]
        assert len(ping_calls) == 0

    @pytest.mark.asyncio
    async def test_heartbeat_ping_failure_does_not_kill_loop(self, manager, mock_websocket):
        """If sending a ping raises, the heartbeat loop continues."""
        conn_id = "conn-ping-fail"
        manager._connections[conn_id] = mock_websocket
        manager._PING_INTERVAL_TICKS = 1

        mock_websocket.send_json = AsyncMock(side_effect=Exception("broken pipe"))

        tick_count = 0
        original_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 3:
                manager._connections.pop(conn_id, None)
            await original_sleep(0)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await manager._heartbeat_loop(conn_id)

        # Loop ran all 3 ticks without crashing (would have raised otherwise)
        assert tick_count == 3
