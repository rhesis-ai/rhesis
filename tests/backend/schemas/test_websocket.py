"""Tests for WebSocket schemas."""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    ConnectionTarget,
    EventType,
    OrgTarget,
    UserTarget,
    WebSocketMessage,
    deserialize_target,
    serialize_target,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_connection_lifecycle_events(self):
        """Test that connection lifecycle events are defined."""
        assert EventType.CONNECTED == "connected"
        assert EventType.DISCONNECTED == "disconnected"
        assert EventType.ERROR == "error"
        assert EventType.PING == "ping"
        assert EventType.PONG == "pong"

    def test_subscription_events(self):
        """Test that subscription events are defined."""
        assert EventType.SUBSCRIBE == "subscribe"
        assert EventType.UNSUBSCRIBE == "unsubscribe"
        assert EventType.SUBSCRIBED == "subscribed"
        assert EventType.UNSUBSCRIBED == "unsubscribed"

    def test_generic_events(self):
        """Test that generic events are defined."""
        assert EventType.NOTIFICATION == "notification"
        assert EventType.MESSAGE == "message"

    def test_event_type_is_string_enum(self):
        """Test that EventType values are strings."""
        for event_type in EventType:
            assert isinstance(event_type.value, str)


class TestWebSocketMessage:
    """Tests for WebSocketMessage schema."""

    def test_minimal_message(self):
        """Test creating a message with only required fields."""
        msg = WebSocketMessage(type=EventType.PING)
        assert msg.type == EventType.PING
        assert msg.channel is None
        assert msg.payload is None
        assert msg.correlation_id is None

    def test_full_message(self):
        """Test creating a message with all fields."""
        msg = WebSocketMessage(
            type=EventType.MESSAGE,
            channel="test_channel",
            payload={"key": "value", "nested": {"data": 123}},
            correlation_id="corr-123",
        )
        assert msg.type == EventType.MESSAGE
        assert msg.channel == "test_channel"
        assert msg.payload == {"key": "value", "nested": {"data": 123}}
        assert msg.correlation_id == "corr-123"

    def test_message_serialization(self):
        """Test that message serializes to JSON correctly."""
        msg = WebSocketMessage(
            type=EventType.CONNECTED,
            payload={"connection_id": "ws_abc123"},
        )
        data = msg.model_dump(mode="json")
        assert data["type"] == "connected"
        assert data["payload"] == {"connection_id": "ws_abc123"}

    def test_message_from_dict(self):
        """Test creating message from dictionary."""
        data = {
            "type": "subscribe",
            "payload": {"channel": "test_run:123"},
        }
        msg = WebSocketMessage(**data)
        assert msg.type == EventType.SUBSCRIBE
        assert msg.payload == {"channel": "test_run:123"}

    def test_invalid_event_type(self):
        """Test that invalid event type raises error."""
        with pytest.raises(ValidationError):
            WebSocketMessage(type="invalid_type")

    def test_empty_payload(self):
        """Test message with empty payload."""
        msg = WebSocketMessage(type=EventType.PING, payload={})
        assert msg.payload == {}

    def test_large_payload(self):
        """Test message with large payload."""
        large_data = {"items": [{"id": i, "data": "x" * 100} for i in range(100)]}
        msg = WebSocketMessage(type=EventType.MESSAGE, payload=large_data)
        assert len(msg.payload["items"]) == 100

    def test_special_characters_in_payload(self):
        """Test message with special characters in payload."""
        msg = WebSocketMessage(
            type=EventType.MESSAGE,
            payload={
                "text": "Hello, 世界! 🌍",
                "emoji": "👍🎉",
                "special": "<script>alert('xss')</script>",
            },
        )
        assert msg.payload["text"] == "Hello, 世界! 🌍"
        assert msg.payload["emoji"] == "👍🎉"


class TestTargetTypes:
    """Tests for target type dataclasses."""

    def test_org_target(self):
        """Test OrgTarget creation."""
        target = OrgTarget(org_id="org-123")
        assert target.org_id == "org-123"

    def test_user_target(self):
        """Test UserTarget creation."""
        target = UserTarget(user_id="user-456")
        assert target.user_id == "user-456"

    def test_channel_target(self):
        """Test ChannelTarget creation."""
        target = ChannelTarget(channel="test_run:789")
        assert target.channel == "test_run:789"

    def test_connection_target(self):
        """Test ConnectionTarget creation."""
        target = ConnectionTarget(connection_id="conn-abc")
        assert target.connection_id == "conn-abc"


class TestTargetSerialization:
    """Tests for target serialization/deserialization."""

    def test_serialize_org_target(self):
        """Test serializing OrgTarget."""
        target = OrgTarget(org_id="org-123")
        data = serialize_target(target)
        assert data == {"type": "org", "org_id": "org-123"}

    def test_serialize_user_target(self):
        """Test serializing UserTarget."""
        target = UserTarget(user_id="user-456")
        data = serialize_target(target)
        assert data == {"type": "user", "user_id": "user-456"}

    def test_serialize_channel_target(self):
        """Test serializing ChannelTarget."""
        target = ChannelTarget(channel="test_run:789")
        data = serialize_target(target)
        assert data == {"type": "channel", "channel": "test_run:789"}

    def test_serialize_connection_target(self):
        """Test serializing ConnectionTarget."""
        target = ConnectionTarget(connection_id="conn-abc")
        data = serialize_target(target)
        assert data == {"type": "connection", "connection_id": "conn-abc"}

    def test_deserialize_org_target(self):
        """Test deserializing OrgTarget."""
        data = {"type": "org", "org_id": "org-123"}
        target = deserialize_target(data)
        assert isinstance(target, OrgTarget)
        assert target.org_id == "org-123"

    def test_deserialize_user_target(self):
        """Test deserializing UserTarget."""
        data = {"type": "user", "user_id": "user-456"}
        target = deserialize_target(data)
        assert isinstance(target, UserTarget)
        assert target.user_id == "user-456"

    def test_deserialize_channel_target(self):
        """Test deserializing ChannelTarget."""
        data = {"type": "channel", "channel": "test_run:789"}
        target = deserialize_target(data)
        assert isinstance(target, ChannelTarget)
        assert target.channel == "test_run:789"

    def test_deserialize_connection_target(self):
        """Test deserializing ConnectionTarget."""
        data = {"type": "connection", "connection_id": "conn-abc"}
        target = deserialize_target(data)
        assert isinstance(target, ConnectionTarget)
        assert target.connection_id == "conn-abc"

    def test_deserialize_unknown_type(self):
        """Test that deserializing unknown type raises error."""
        with pytest.raises(ValueError, match="Unknown target type"):
            deserialize_target({"type": "unknown", "id": "123"})

    def test_roundtrip_serialization(self):
        """Test that serialize/deserialize is a roundtrip."""
        targets = [
            OrgTarget(org_id="org-123"),
            UserTarget(user_id="user-456"),
            ChannelTarget(channel="test_run:789"),
            ConnectionTarget(connection_id="conn-abc"),
        ]
        for original in targets:
            serialized = serialize_target(original)
            deserialized = deserialize_target(serialized)
            assert type(deserialized) is type(original)
            # Compare by serializing both - dataclasses may have different instances
            assert serialize_target(deserialized) == serialized
