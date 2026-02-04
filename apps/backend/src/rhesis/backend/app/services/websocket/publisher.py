"""Event publisher for WebSocket broadcasting.

This module provides the EventPublisher class that publishes events via Redis
for cross-instance broadcasting. It provides both sync and async interfaces
to support use from both Celery workers and FastAPI endpoints.
"""

import json
import logging
import os
from typing import Optional

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from rhesis.backend.app.schemas.websocket import (
    Target,
    WebSocketMessage,
    serialize_target,
)

logger = logging.getLogger(__name__)

# Redis channel for WebSocket events
WS_EVENTS_CHANNEL = "ws:events"


class EventPublisher:
    """Publishes WebSocket events via Redis pub/sub.

    This publisher supports both synchronous and asynchronous publishing:
    - Sync: For use in Celery workers and synchronous code
    - Async: For use in FastAPI endpoints and async code

    Events are published to Redis, where WebSocketManager instances
    (potentially on different backend instances) pick them up and
    broadcast to locally connected clients.

    Example:
        # Sync usage (Celery tasks)
        publisher = get_publisher()
        publisher.publish(message, ChannelTarget(channel="test_run:123"))

        # Async usage (FastAPI endpoints)
        await publisher.publish_async(message, OrgTarget(org_id="org-123"))

        # Or use convenience functions
        publish_event(message, target)  # sync
        await publish_event_async(message, target)  # async
    """

    def __init__(self, redis_url: str):
        """Initialize the event publisher.

        Args:
            redis_url: Redis connection URL.
        """
        self._redis_url = redis_url
        self._sync_redis: Optional[Redis] = None
        self._async_redis: Optional[AsyncRedis] = None

    def _get_sync_redis(self) -> Redis:
        """Get or create the sync Redis client.

        Returns:
            Synchronous Redis client.
        """
        if self._sync_redis is None:
            self._sync_redis = Redis.from_url(self._redis_url)
        return self._sync_redis

    async def _get_async_redis(self) -> AsyncRedis:
        """Get or create the async Redis client.

        Returns:
            Asynchronous Redis client.
        """
        if self._async_redis is None:
            self._async_redis = AsyncRedis.from_url(self._redis_url)
        return self._async_redis

    def publish(self, message: WebSocketMessage, target: Target) -> int:
        """Publish an event to Redis (synchronous).

        Use this method from Celery workers or other synchronous code.

        Args:
            message: The WebSocket message to publish.
            target: The broadcast target.

        Returns:
            Number of subscribers that received the message.
        """
        payload = self._serialize_event(message, target)
        redis = self._get_sync_redis()

        try:
            result = redis.publish(WS_EVENTS_CHANNEL, payload)
            logger.debug(
                f"Published event {message.type} to {WS_EVENTS_CHANNEL} (subscribers: {result})"
            )
            return result
        except Exception as e:
            logger.error(f"Failed to publish event to Redis: {e}")
            return 0

    async def publish_async(self, message: WebSocketMessage, target: Target) -> int:
        """Publish an event to Redis (asynchronous).

        Use this method from FastAPI endpoints or other async code.

        Args:
            message: The WebSocket message to publish.
            target: The broadcast target.

        Returns:
            Number of subscribers that received the message.
        """
        payload = self._serialize_event(message, target)
        redis = await self._get_async_redis()

        try:
            result = await redis.publish(WS_EVENTS_CHANNEL, payload)
            logger.debug(
                f"Published event {message.type} to {WS_EVENTS_CHANNEL} (subscribers: {result})"
            )
            return result
        except Exception as e:
            logger.error(f"Failed to publish event to Redis: {e}")
            return 0

    def _serialize_event(self, message: WebSocketMessage, target: Target) -> str:
        """Serialize an event for Redis transmission.

        Args:
            message: The WebSocket message.
            target: The broadcast target.

        Returns:
            JSON-encoded event payload.
        """
        payload = {
            "message": message.model_dump(mode="json"),
            "target": serialize_target(target),
        }
        return json.dumps(payload)

    def close(self) -> None:
        """Close Redis connections."""
        if self._sync_redis:
            self._sync_redis.close()
            self._sync_redis = None

    async def close_async(self) -> None:
        """Close async Redis connections."""
        if self._async_redis:
            await self._async_redis.close()
            self._async_redis = None


# Singleton instance
_publisher: Optional[EventPublisher] = None


def get_publisher() -> EventPublisher:
    """Get or create the event publisher singleton.

    The publisher is lazily initialized using the REDIS_URL environment variable.

    Returns:
        The EventPublisher singleton instance.
    """
    global _publisher
    if _publisher is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _publisher = EventPublisher(redis_url)
    return _publisher


def publish_event(message: WebSocketMessage, target: Target) -> int:
    """Publish an event to Redis (synchronous convenience function).

    Use this from Celery workers or other synchronous code.

    Args:
        message: The WebSocket message to publish.
        target: The broadcast target.

    Returns:
        Number of subscribers that received the message.

    Example:
        publish_event(
            WebSocketMessage(type=EventType.NOTIFICATION, payload={"msg": "Hello"}),
            OrgTarget(org_id="org-123")
        )
    """
    return get_publisher().publish(message, target)


async def publish_event_async(message: WebSocketMessage, target: Target) -> int:
    """Publish an event to Redis (asynchronous convenience function).

    Use this from FastAPI endpoints or other async code.

    Args:
        message: The WebSocket message to publish.
        target: The broadcast target.

    Returns:
        Number of subscribers that received the message.

    Example:
        await publish_event_async(
            WebSocketMessage(type=EventType.NOTIFICATION, payload={"msg": "Hello"}),
            UserTarget(user_id="user-456")
        )
    """
    return await get_publisher().publish_async(message, target)
