"""Redis client for SDK RPC communication between workers and backend."""

import logging
import time

import redis.asyncio as redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from rhesis.backend.app.config.settings import get_redis_settings

logger = logging.getLogger(__name__)

# Seconds to wait before retrying after a failed connection attempt.
# Prevents hammering Redis during an outage while ensuring self-healing
# once the service recovers (closes #2272).
_RETRY_COOLDOWN_SECONDS = 30

# Ping a pooled connection that has been idle this long before reusing it,
# so a connection the server already dropped is replaced instead of used.
_HEALTH_CHECK_INTERVAL_SECONDS = 30

# Per-command reconnect attempts on a dropped connection.
_COMMAND_RETRIES = 3


class RedisConnectionManager:
    """Manages Redis connection for SDK RPC with graceful fallback."""

    def __init__(self):
        """Initialize Redis connection manager."""
        self._client = None
        self._initialized = False
        self._last_failed_at: float = 0

    async def initialize(self):
        """
        Initialize Redis connection.

        Attempts to connect but doesn't raise on failure.
        After a failure, retries are throttled by _RETRY_COOLDOWN_SECONDS
        so a transient outage self-heals without hammering Redis.
        """
        if self._initialized:
            return

        # Throttle retries after a failure — don't hammer Redis
        now = time.monotonic()
        if self._last_failed_at and (now - self._last_failed_at) < _RETRY_COOLDOWN_SECONDS:
            return

        try:
            redis_url = get_redis_settings().broker_url
            self._client = await redis.from_url(
                redis_url,
                decode_responses=True,
                encoding="utf-8",
                max_connections=3,
                health_check_interval=_HEALTH_CHECK_INTERVAL_SECONDS,
                socket_keepalive=True,
                retry=Retry(ExponentialBackoff(cap=1.0, base=0.05), _COMMAND_RETRIES),
                # Without retry_on_error redis-py raises a dropped connection at the
                # call site instead of reconnecting, which floods the RPC listener's
                # blpop loop with ConnectionError (closes #1695).
                retry_on_error=[RedisConnectionError, RedisTimeoutError],
            )
            # Actually test the connection - from_url() doesn't connect until first use
            await self._client.ping()
            self._initialized = True
            self._last_failed_at = 0  # reset cooldown on success
            logger.info("Redis connection established for SDK RPC")
        except Exception as e:
            self._last_failed_at = time.monotonic()
            if self._client:
                try:
                    await self._client.close()
                except Exception:
                    pass
                self._client = None
            logger.warning(
                f"Redis not available: {e}. SDK RPC via worker will not work. "
                f"Retrying in {_RETRY_COOLDOWN_SECONDS}s."
            )

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
