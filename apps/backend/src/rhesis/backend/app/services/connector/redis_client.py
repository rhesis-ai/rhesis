"""Redis client for SDK RPC communication between workers and backend."""

import logging
import os

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """Manages Redis connection for SDK RPC with graceful fallback."""

    def __init__(self):
        """Initialize Redis connection manager."""
        self._client = None
        self._initialized = False
        self._initialization_failed = False

    async def initialize(self):
        """
        Initialize Redis connection.

        Attempts to connect but doesn't raise on failure.
        Logs warning if connection fails.
        """
        if self._initialized or self._initialization_failed:
            return

        try:
            redis_url = os.getenv("BROKER_URL", "redis://localhost:6379/0")
            self._client = await redis.from_url(redis_url, decode_responses=True, encoding="utf-8")
            # Actually test the connection - from_url() doesn't connect until first use
            await self._client.ping()
            self._initialized = True
            logger.info("Redis connection established for SDK RPC")
        except Exception as e:
            self._initialization_failed = True
            if self._client:
                try:
                    await self._client.close()
                except Exception:
                    pass
                self._client = None
            logger.warning(f"Redis not available: {e}. SDK RPC via worker will not work.")

    async def close(self):
        """Close Redis connection if open."""
        if self._client:
            await self._client.close()
            logger.info("Redis connection closed")

    @property
    def client(self):
        """
        Get Redis client.

        Raises:
            RuntimeError: If Redis not initialized

        Returns:
            Redis client instance
        """
        if not self._initialized:
            raise RuntimeError("Redis not initialized. Cannot use SDK RPC from workers.")
        return self._client

    @property
    def is_available(self) -> bool:
        """
        Check if Redis is available.

        Returns:
            True if Redis connection is established and available
        """
        return self._initialized and self._client is not None


# Global Redis manager instance
redis_manager = RedisConnectionManager()
