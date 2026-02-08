"""Redis pub/sub integration for WebSocket broadcasting.

This module provides the RedisSubscriber class that listens for events
published to Redis and forwards them to the WebSocketManager for
local broadcasting. This enables multi-instance deployments where
events published on one instance are broadcast to clients connected
to any instance.
"""

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Optional

from redis.asyncio import Redis as AsyncRedis

from rhesis.backend.app.schemas.websocket import (
    WebSocketMessage,
    deserialize_target,
)
from rhesis.backend.app.services.websocket.publisher import WS_EVENTS_CHANNEL

if TYPE_CHECKING:
    from rhesis.backend.app.services.websocket.manager import WebSocketManager

logger = logging.getLogger(__name__)


class RedisSubscriber:
    """Subscribes to Redis pub/sub and forwards events to WebSocketManager.

    This class enables multi-instance WebSocket support by:
    1. Subscribing to a Redis channel for events
    2. Deserializing received events
    3. Forwarding them to the local WebSocketManager for broadcasting

    The subscriber runs as a background task and automatically reconnects
    on connection failures.

    Example:
        subscriber = RedisSubscriber(ws_manager)
        await subscriber.start()

        # Later, when shutting down
        await subscriber.stop()
    """

    def __init__(
        self,
        ws_manager: "WebSocketManager",
        redis_url: Optional[str] = None,
    ):
        """Initialize the Redis subscriber.

        Args:
            ws_manager: The WebSocketManager to forward events to.
            redis_url: Redis connection URL. If not provided, uses REDIS_URL env var.
        """
        self._ws_manager = ws_manager
        # Check BROKER_URL first for consistency with other Redis consumers, then REDIS_URL
        self._redis_url = (
            redis_url
            or os.environ.get("BROKER_URL")
            or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        )
        self._redis: Optional[AsyncRedis] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the Redis subscriber.

        This starts a background task that listens for events on the
        Redis channel and forwards them to the WebSocketManager.
        """
        if self._running:
            logger.warning("Redis subscriber already running")
            return

        self._running = True
        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info(f"Redis subscriber started, listening on {WS_EVENTS_CHANNEL}")

    async def stop(self) -> None:
        """Stop the Redis subscriber.

        This cancels the background listener task and closes the Redis connection.
        """
        self._running = False

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        if self._redis:
            await self._redis.close()
            self._redis = None

        logger.info("Redis subscriber stopped")

    async def _listen_loop(self) -> None:
        """Main listener loop that processes Redis events.

        This loop automatically reconnects on connection failures with
        exponential backoff.
        """
        retry_delay = 1.0
        max_retry_delay = 60.0

        while self._running:
            try:
                await self._connect_and_listen()
                # Reset retry delay on successful connection
                retry_delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # Log at debug level to avoid noisy logs when Redis isn't available
                # (common in local development)
                logger.debug(f"Redis subscriber error: {e}")
                if self._running:
                    logger.debug(f"Reconnecting in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_retry_delay)

    async def _connect_and_listen(self) -> None:
        """Connect to Redis and listen for events."""
        self._redis = AsyncRedis.from_url(self._redis_url)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(WS_EVENTS_CHANNEL)

        logger.debug(f"Subscribed to Redis channel: {WS_EVENTS_CHANNEL}")

        async for message in pubsub.listen():
            if not self._running:
                break

            if message["type"] != "message":
                continue

            try:
                await self._handle_message(message["data"])
            except Exception as e:
                logger.error(f"Error handling Redis message: {e}")

    async def _handle_message(self, data: bytes) -> None:
        """Handle a message received from Redis.

        Args:
            data: Raw message data from Redis.
        """
        try:
            # Parse the JSON payload
            payload = json.loads(data)

            # Deserialize message and target
            message = WebSocketMessage(**payload["message"])
            target = deserialize_target(payload["target"])

            # Forward to WebSocketManager
            sent_count = await self._ws_manager.broadcast(message, target)

            logger.debug(f"Forwarded Redis event {message.type} to {sent_count} connections")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Redis message: {e}")
        except KeyError as e:
            logger.error(f"Missing field in Redis message: {e}")
        except Exception as e:
            logger.error(f"Error processing Redis message: {e}")

    @property
    def is_running(self) -> bool:
        """Check if the subscriber is running."""
        return self._running


# Singleton instance
_subscriber: Optional[RedisSubscriber] = None


def get_subscriber(ws_manager: "WebSocketManager") -> RedisSubscriber:
    """Get or create the Redis subscriber singleton.

    Args:
        ws_manager: The WebSocketManager to forward events to.

    Returns:
        The RedisSubscriber singleton instance.
    """
    global _subscriber
    if _subscriber is None:
        _subscriber = RedisSubscriber(ws_manager)
    return _subscriber


async def start_redis_subscriber(ws_manager: "WebSocketManager") -> RedisSubscriber:
    """Start the Redis subscriber.

    This is a convenience function for starting the Redis subscriber
    during application startup.

    Args:
        ws_manager: The WebSocketManager to forward events to.

    Returns:
        The started RedisSubscriber instance.
    """
    subscriber = get_subscriber(ws_manager)
    await subscriber.start()
    return subscriber


async def stop_redis_subscriber() -> None:
    """Stop the Redis subscriber.

    This is a convenience function for stopping the Redis subscriber
    during application shutdown.
    """
    global _subscriber
    if _subscriber:
        await _subscriber.stop()
        _subscriber = None
