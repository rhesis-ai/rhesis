"""Tests for EventPublisher."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    ConnectionTarget,
    EventType,
    OrgTarget,
    UserTarget,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.publisher import (
    WS_EVENTS_CHANNEL,
    EventPublisher,
    get_publisher,
    publish_event,
    publish_event_async,
)


@pytest.fixture
def mock_sync_redis():
    """Create a mock sync Redis client."""
    redis = MagicMock()
    redis.publish = MagicMock(return_value=1)
    return redis


@pytest.fixture
def mock_async_redis():
    """Create a mock async Redis client."""
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def publisher():
    """Create a fresh EventPublisher instance."""
    return EventPublisher(redis_url="redis://localhost:6379/0")


class TestEventPublisher:
    """Tests for EventPublisher class."""

    def test_serialize_event_with_org_target(self, publisher):
        """Test serializing event with OrgTarget."""
        msg = WebSocketMessage(type=EventType.MESSAGE, payload={"data": "test"})
        target = OrgTarget(org_id="org-123")

        result = publisher._serialize_event(msg, target)
        data = json.loads(result)

        assert data["message"]["type"] == "message"
        assert data["message"]["payload"] == {"data": "test"}
        assert data["target"]["type"] == "org"
        assert data["target"]["org_id"] == "org-123"

    def test_serialize_event_with_user_target(self, publisher):
        """Test serializing event with UserTarget."""
        msg = WebSocketMessage(type=EventType.NOTIFICATION, payload={"alert": "hello"})
        target = UserTarget(user_id="user-456")

        result = publisher._serialize_event(msg, target)
        data = json.loads(result)

        assert data["message"]["type"] == "notification"
        assert data["target"]["type"] == "user"
        assert data["target"]["user_id"] == "user-456"

    def test_serialize_event_with_channel_target(self, publisher):
        """Test serializing event with ChannelTarget."""
        msg = WebSocketMessage(type=EventType.MESSAGE, channel="test_run:123")
        target = ChannelTarget(channel="test_run:123")

        result = publisher._serialize_event(msg, target)
        data = json.loads(result)

        assert data["target"]["type"] == "channel"
        assert data["target"]["channel"] == "test_run:123"

    def test_serialize_event_with_connection_target(self, publisher):
        """Test serializing event with ConnectionTarget."""
        msg = WebSocketMessage(type=EventType.PONG)
        target = ConnectionTarget(connection_id="conn-abc")

        result = publisher._serialize_event(msg, target)
        data = json.loads(result)

        assert data["target"]["type"] == "connection"
        assert data["target"]["connection_id"] == "conn-abc"

    def test_publish_sync(self, publisher, mock_sync_redis):
        """Test synchronous publish."""
        publisher._sync_redis = mock_sync_redis

        msg = WebSocketMessage(type=EventType.MESSAGE, payload={"data": "test"})
        target = OrgTarget(org_id="org-123")

        result = publisher.publish(msg, target)

        assert result == 1
        mock_sync_redis.publish.assert_called_once()
        call_args = mock_sync_redis.publish.call_args
        assert call_args[0][0] == WS_EVENTS_CHANNEL
        # Verify payload is valid JSON
        payload = json.loads(call_args[0][1])
        assert payload["message"]["type"] == "message"

    def test_publish_sync_error(self, publisher, mock_sync_redis):
        """Test synchronous publish handles errors."""
        mock_sync_redis.publish.side_effect = Exception("Connection error")
        publisher._sync_redis = mock_sync_redis

        msg = WebSocketMessage(type=EventType.MESSAGE)
        target = OrgTarget(org_id="org-123")

        result = publisher.publish(msg, target)

        assert result == 0

    @pytest.mark.asyncio
    async def test_publish_async(self, publisher, mock_async_redis):
        """Test asynchronous publish."""
        publisher._async_redis = mock_async_redis

        msg = WebSocketMessage(type=EventType.NOTIFICATION, payload={"alert": "test"})
        target = UserTarget(user_id="user-456")

        result = await publisher.publish_async(msg, target)

        assert result == 1
        mock_async_redis.publish.assert_called_once()
        call_args = mock_async_redis.publish.call_args
        assert call_args[0][0] == WS_EVENTS_CHANNEL

    @pytest.mark.asyncio
    async def test_publish_async_error(self, publisher, mock_async_redis):
        """Test asynchronous publish handles errors."""
        mock_async_redis.publish.side_effect = Exception("Connection error")
        publisher._async_redis = mock_async_redis

        msg = WebSocketMessage(type=EventType.MESSAGE)
        target = OrgTarget(org_id="org-123")

        result = await publisher.publish_async(msg, target)

        assert result == 0

    def test_close(self, publisher, mock_sync_redis):
        """Test closing sync Redis connection."""
        publisher._sync_redis = mock_sync_redis

        publisher.close()

        mock_sync_redis.close.assert_called_once()
        assert publisher._sync_redis is None

    @pytest.mark.asyncio
    async def test_close_async(self, publisher, mock_async_redis):
        """Test closing async Redis connection."""
        publisher._async_redis = mock_async_redis

        await publisher.close_async()

        mock_async_redis.close.assert_called_once()
        assert publisher._async_redis is None


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @patch("rhesis.backend.app.services.websocket.publisher.get_publisher")
    def test_publish_event(self, mock_get_publisher):
        """Test publish_event convenience function."""
        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = 1
        mock_get_publisher.return_value = mock_publisher

        msg = WebSocketMessage(type=EventType.MESSAGE)
        target = OrgTarget(org_id="org-123")

        result = publish_event(msg, target)

        assert result == 1
        mock_publisher.publish.assert_called_once_with(msg, target)

    @pytest.mark.asyncio
    @patch("rhesis.backend.app.services.websocket.publisher.get_publisher")
    async def test_publish_event_async(self, mock_get_publisher):
        """Test publish_event_async convenience function."""
        mock_publisher = MagicMock()
        mock_publisher.publish_async = AsyncMock(return_value=1)
        mock_get_publisher.return_value = mock_publisher

        msg = WebSocketMessage(type=EventType.NOTIFICATION)
        target = UserTarget(user_id="user-456")

        result = await publish_event_async(msg, target)

        assert result == 1
        mock_publisher.publish_async.assert_called_once_with(msg, target)


class TestGetPublisher:
    """Tests for get_publisher function."""

    def test_get_publisher_creates_instance(self):
        """Test that get_publisher creates a new instance using BROKER_URL."""
        import os

        from rhesis.backend.app.services.websocket import publisher as publisher_module

        # Save original state
        original_publisher = publisher_module._publisher
        original_broker = os.environ.get("BROKER_URL")
        original_redis = os.environ.get("REDIS_URL")

        try:
            # Reset singleton and set test env vars
            publisher_module._publisher = None
            os.environ.pop("BROKER_URL", None)
            os.environ.pop("REDIS_URL", None)
            os.environ["BROKER_URL"] = "redis://test:6379/1"

            publisher = get_publisher()

            assert publisher is not None
            assert isinstance(publisher, EventPublisher)
            assert publisher._redis_url == "redis://test:6379/1"
        finally:
            # Restore original state
            publisher_module._publisher = original_publisher
            os.environ.pop("BROKER_URL", None)
            os.environ.pop("REDIS_URL", None)
            if original_broker:
                os.environ["BROKER_URL"] = original_broker
            if original_redis:
                os.environ["REDIS_URL"] = original_redis

    def test_get_publisher_default_url(self):
        """Test that get_publisher uses default URL when env vars not set."""
        import os

        from rhesis.backend.app.services.websocket import publisher as publisher_module

        # Save original state
        original_publisher = publisher_module._publisher
        original_broker = os.environ.get("BROKER_URL")
        original_redis = os.environ.get("REDIS_URL")

        try:
            # Reset singleton and clear env vars
            publisher_module._publisher = None
            os.environ.pop("BROKER_URL", None)
            os.environ.pop("REDIS_URL", None)

            publisher = get_publisher()
            assert publisher._redis_url == "redis://localhost:6379/0"
        finally:
            # Restore original state
            publisher_module._publisher = original_publisher
            if original_broker:
                os.environ["BROKER_URL"] = original_broker
            if original_redis:
                os.environ["REDIS_URL"] = original_redis

    @patch("rhesis.backend.app.services.websocket.publisher._publisher")
    def test_get_publisher_returns_singleton(self, mock_publisher):
        """Test that get_publisher returns the same instance."""
        mock_instance = MagicMock()
        mock_publisher.__bool__ = MagicMock(return_value=True)

        # When _publisher is not None, it should return the existing instance
        import rhesis.backend.app.services.websocket.publisher as publisher_module

        publisher_module._publisher = mock_instance

        result = get_publisher()
        assert result is mock_instance
