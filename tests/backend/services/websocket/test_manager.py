"""Tests for WebSocketManager."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    ConnectionTarget,
    EventType,
    OrgTarget,
    UserTarget,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.manager import WebSocketManager
from rhesis.backend.app.services.websocket.registry import ConnectionRegistry


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock()
    user.id = uuid4()
    user.organization_id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket object."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def manager():
    """Create a fresh WebSocketManager instance."""
    return WebSocketManager()


class TestConnectionRegistry:
    """Tests for ConnectionRegistry."""

    def test_add_and_get_by_id(self, mock_websocket, mock_user):
        """Test adding a connection and retrieving by ID."""
        registry = ConnectionRegistry()
        registry.add(
            conn_id="conn-1",
            websocket=mock_websocket,
            user_id=str(mock_user.id),
            org_id=str(mock_user.organization_id),
        )

        ws = registry.get_by_id("conn-1")
        assert ws is mock_websocket

    def test_get_by_id_not_found(self):
        """Test getting a non-existent connection."""
        registry = ConnectionRegistry()
        assert registry.get_by_id("nonexistent") is None

    def test_remove_connection(self, mock_websocket, mock_user):
        """Test removing a connection."""
        registry = ConnectionRegistry()
        registry.add(
            conn_id="conn-1",
            websocket=mock_websocket,
            user_id=str(mock_user.id),
            org_id=str(mock_user.organization_id),
        )

        conn_info = registry.remove("conn-1")
        assert conn_info is not None
        assert registry.get_by_id("conn-1") is None

    def test_get_by_org(self, mock_websocket, mock_user):
        """Test getting connections by organization."""
        registry = ConnectionRegistry()
        org_id = str(mock_user.organization_id)

        # Add two connections for same org
        registry.add("conn-1", mock_websocket, str(mock_user.id), org_id)
        ws2 = AsyncMock()
        registry.add("conn-2", ws2, str(uuid4()), org_id)

        connections = registry.get_by_org(org_id)
        assert len(connections) == 2
        assert mock_websocket in connections
        assert ws2 in connections

    def test_get_by_user(self, mock_websocket, mock_user):
        """Test getting connections by user."""
        registry = ConnectionRegistry()
        user_id = str(mock_user.id)
        org_id = str(mock_user.organization_id)

        # Add two connections for same user (multiple tabs)
        registry.add("conn-1", mock_websocket, user_id, org_id)
        ws2 = AsyncMock()
        registry.add("conn-2", ws2, user_id, org_id)

        connections = registry.get_by_user(user_id)
        assert len(connections) == 2

    def test_subscription_management(self, mock_websocket, mock_user):
        """Test adding and removing channel subscriptions."""
        registry = ConnectionRegistry()
        registry.add(
            conn_id="conn-1",
            websocket=mock_websocket,
            user_id=str(mock_user.id),
            org_id=str(mock_user.organization_id),
        )

        # Add subscription
        assert registry.add_subscription("conn-1", "test_channel") is True
        assert "test_channel" in registry.get_subscriptions("conn-1")

        # Get by channel
        connections = registry.get_by_channel("test_channel")
        assert len(connections) == 1
        assert mock_websocket in connections

        # Remove subscription
        assert registry.remove_subscription("conn-1", "test_channel") is True
        assert "test_channel" not in registry.get_subscriptions("conn-1")
        assert len(registry.get_by_channel("test_channel")) == 0

    def test_cleanup_on_remove(self, mock_websocket, mock_user):
        """Test that all indexes are cleaned up on connection removal."""
        registry = ConnectionRegistry()
        user_id = str(mock_user.id)
        org_id = str(mock_user.organization_id)

        registry.add("conn-1", mock_websocket, user_id, org_id)
        registry.add_subscription("conn-1", "channel-1")
        registry.add_subscription("conn-1", "channel-2")

        # Remove connection
        registry.remove("conn-1")

        # Verify cleanup
        assert registry.get_by_id("conn-1") is None
        assert len(registry.get_by_user(user_id)) == 0
        assert len(registry.get_by_org(org_id)) == 0
        assert len(registry.get_by_channel("channel-1")) == 0
        assert len(registry.get_by_channel("channel-2")) == 0

    def test_connection_count(self, mock_websocket, mock_user):
        """Test connection count property."""
        registry = ConnectionRegistry()
        assert registry.connection_count == 0

        registry.add("conn-1", mock_websocket, str(mock_user.id), str(mock_user.organization_id))
        assert registry.connection_count == 1

        registry.add("conn-2", AsyncMock(), str(uuid4()), str(uuid4()))
        assert registry.connection_count == 2

        registry.remove("conn-1")
        assert registry.connection_count == 1


class TestWebSocketManagerConnect:
    """Tests for WebSocketManager connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect(self, manager, mock_websocket, mock_user):
        """Test successful connection."""
        conn_id = await manager.connect(mock_websocket, mock_user)

        assert conn_id is not None
        assert conn_id.startswith("ws_")
        assert manager.connection_count == 1

    @pytest.mark.asyncio
    async def test_disconnect(self, manager, mock_websocket, mock_user):
        """Test disconnection."""
        conn_id = await manager.connect(mock_websocket, mock_user)
        manager.disconnect(conn_id)

        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_unknown_connection(self, manager):
        """Test disconnecting an unknown connection."""
        # Should not raise
        manager.disconnect("unknown-conn")


class TestWebSocketManagerSubscriptions:
    """Tests for WebSocketManager subscription management."""

    @pytest.mark.asyncio
    async def test_subscribe(self, manager, mock_websocket, mock_user):
        """Test subscribing to a channel."""
        conn_id = await manager.connect(mock_websocket, mock_user)
        assert manager.subscribe(conn_id, "test_channel") is True
        assert "test_channel" in manager.get_subscriptions(conn_id)

    @pytest.mark.asyncio
    async def test_unsubscribe(self, manager, mock_websocket, mock_user):
        """Test unsubscribing from a channel."""
        conn_id = await manager.connect(mock_websocket, mock_user)
        manager.subscribe(conn_id, "test_channel")
        assert manager.unsubscribe(conn_id, "test_channel") is True
        assert "test_channel" not in manager.get_subscriptions(conn_id)

    @pytest.mark.asyncio
    async def test_subscribe_invalid_connection(self, manager):
        """Test subscribing with invalid connection ID."""
        assert manager.subscribe("invalid", "channel") is False


class TestWebSocketManagerBroadcast:
    """Tests for WebSocketManager broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcast_to_org(self, manager, mock_websocket, mock_user):
        """Test broadcasting to an organization."""
        await manager.connect(mock_websocket, mock_user)

        msg = WebSocketMessage(type=EventType.MESSAGE, payload={"data": "test"})
        sent = await manager.broadcast(msg, OrgTarget(org_id=str(mock_user.organization_id)))

        assert sent == 1
        mock_websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_user(self, manager, mock_websocket, mock_user):
        """Test broadcasting to a specific user."""
        await manager.connect(mock_websocket, mock_user)

        msg = WebSocketMessage(type=EventType.NOTIFICATION, payload={"alert": "hello"})
        sent = await manager.broadcast(msg, UserTarget(user_id=str(mock_user.id)))

        assert sent == 1
        mock_websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_channel(self, manager, mock_websocket, mock_user):
        """Test broadcasting to a channel."""
        conn_id = await manager.connect(mock_websocket, mock_user)
        manager.subscribe(conn_id, "test_channel")

        msg = WebSocketMessage(type=EventType.MESSAGE, payload={"update": "new"})
        sent = await manager.broadcast(msg, ChannelTarget(channel="test_channel"))

        assert sent == 1
        mock_websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_connection(self, manager, mock_websocket, mock_user):
        """Test broadcasting to a specific connection."""
        conn_id = await manager.connect(mock_websocket, mock_user)

        msg = WebSocketMessage(type=EventType.PONG)
        sent = await manager.broadcast(msg, ConnectionTarget(connection_id=conn_id))

        assert sent == 1
        mock_websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_no_connections(self, manager):
        """Test broadcasting when no connections match."""
        msg = WebSocketMessage(type=EventType.MESSAGE)
        sent = await manager.broadcast(msg, OrgTarget(org_id="nonexistent"))

        assert sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_handles_send_failure(self, manager, mock_websocket, mock_user):
        """Test that broadcast handles send failures gracefully."""
        mock_websocket.send_json.side_effect = Exception("Connection closed")
        conn_id = await manager.connect(mock_websocket, mock_user)

        msg = WebSocketMessage(type=EventType.MESSAGE)
        sent = await manager.broadcast(msg, ConnectionTarget(connection_id=conn_id))

        # Should not raise, but return 0 sent
        assert sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_connections(self, manager, mock_user):
        """Test broadcasting to multiple connections."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect(ws1, mock_user)
        await manager.connect(ws2, mock_user)

        msg = WebSocketMessage(type=EventType.MESSAGE)
        sent = await manager.broadcast(msg, UserTarget(user_id=str(mock_user.id)))

        assert sent == 2
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()


class TestWebSocketManagerMessageHandling:
    """Tests for WebSocketManager message handling."""

    @pytest.mark.asyncio
    async def test_handle_subscribe_message(self, manager, mock_websocket, mock_user):
        """Test handling SUBSCRIBE message."""
        conn_id = await manager.connect(mock_websocket, mock_user)

        # Use a valid channel format that the user is authorized to subscribe to
        valid_channel = f"user:{mock_user.id}"
        msg = WebSocketMessage(
            type=EventType.SUBSCRIBE,
            payload={"channel": valid_channel},
        )
        await manager.handle_message(conn_id, mock_user, msg)

        # Should subscribe and send confirmation
        assert valid_channel in manager.get_subscriptions(conn_id)
        assert mock_websocket.send_json.called

    @pytest.mark.asyncio
    async def test_handle_unsubscribe_message(self, manager, mock_websocket, mock_user):
        """Test handling UNSUBSCRIBE message."""
        conn_id = await manager.connect(mock_websocket, mock_user)
        manager.subscribe(conn_id, "test_channel")
        mock_websocket.send_json.reset_mock()

        msg = WebSocketMessage(
            type=EventType.UNSUBSCRIBE,
            payload={"channel": "test_channel"},
        )
        await manager.handle_message(conn_id, mock_user, msg)

        assert "test_channel" not in manager.get_subscriptions(conn_id)
        assert mock_websocket.send_json.called

    @pytest.mark.asyncio
    async def test_handle_ping_message(self, manager, mock_websocket, mock_user):
        """Test handling PING message."""
        conn_id = await manager.connect(mock_websocket, mock_user)
        mock_websocket.send_json.reset_mock()

        msg = WebSocketMessage(type=EventType.PING)
        await manager.handle_message(conn_id, mock_user, msg)

        # Should respond with PONG
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == EventType.PONG.value

    @pytest.mark.asyncio
    async def test_handle_subscribe_missing_channel(self, manager, mock_websocket, mock_user):
        """Test handling SUBSCRIBE without channel sends error."""
        conn_id = await manager.connect(mock_websocket, mock_user)
        mock_websocket.send_json.reset_mock()

        msg = WebSocketMessage(type=EventType.SUBSCRIBE, payload={})
        await manager.handle_message(conn_id, mock_user, msg)

        # Should send error
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == EventType.ERROR.value


class TestWebSocketManagerStats:
    """Tests for WebSocketManager statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, manager, mock_websocket, mock_user):
        """Test getting manager statistics."""
        await manager.connect(mock_websocket, mock_user)

        stats = manager.get_stats()
        assert stats["total_connections"] == 1
        assert stats["organizations"] == 1
        assert stats["users"] == 1
        assert stats["channels"] == 0

    @pytest.mark.asyncio
    async def test_get_connection_info(self, manager, mock_websocket, mock_user):
        """Test getting connection info."""
        conn_id = await manager.connect(mock_websocket, mock_user)

        info = manager.get_connection_info(conn_id)
        assert info is not None
        assert info.user_id == str(mock_user.id)
        assert info.org_id == str(mock_user.organization_id)
