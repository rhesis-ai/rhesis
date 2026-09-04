"""
Regression test for Redis retry-latch bug (closes #2272).

Before the fix, RedisConnectionManager.initialize() set a permanent
_initialization_failed flag on first failure, preventing all future
retries. A pod whose first Redis ping failed during a brief outage
would reject every login for its entire lifetime.

The fix replaces the permanent latch with a time-based cooldown
(_RETRY_COOLDOWN_SECONDS), so the manager self-heals once Redis
recovers.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_redis_settings():
    """Mock Redis settings to avoid needing real config."""
    settings = MagicMock()
    settings.broker_url = "redis://localhost:6379/0"
    return settings


@pytest.fixture
def redis_manager():
    """Create a fresh RedisConnectionManager for each test."""
    from rhesis.backend.app.services.connector.redis_client import (
        RedisConnectionManager,
    )

    return RedisConnectionManager()


class TestRedisRetryCooldown:
    """Verify the cooldown-based retry logic."""

    @pytest.mark.asyncio
    async def test_first_failure_does_not_latch(self, redis_manager, mock_redis_settings):
        """After first failure, _initialization_failed must NOT be permanent."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_client.close = AsyncMock()

        with (
            patch(
                "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
                return_value=mock_redis_settings,
            ),
            patch(
                "rhesis.backend.app.services.connector.redis_client.create_client",
                return_value=mock_client,
            ),
        ):
            await redis_manager.initialize()

        # After failure: not initialized, but NOT permanently latched
        assert not redis_manager._initialized
        assert redis_manager._last_failed_at > 0
        # The old _initialization_failed attribute must not exist
        assert not hasattr(redis_manager, "_initialization_failed")

    @pytest.mark.asyncio
    async def test_retry_after_cooldown(self, redis_manager, mock_redis_settings):
        """After cooldown expires, initialize() must retry and succeed."""
        # First attempt: fail
        mock_client_fail = AsyncMock()
        mock_client_fail.ping = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_client_fail.close = AsyncMock()

        def _build_failing(*args, **kwargs):
            return mock_client_fail

        with (
            patch(
                "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
                return_value=mock_redis_settings,
            ),
            patch(
                "rhesis.backend.app.services.connector.redis_client.create_client",
                side_effect=_build_failing,
            ),
        ):
            await redis_manager.initialize()
        assert not redis_manager._initialized

        # Simulate cooldown expiry
        redis_manager._last_failed_at = time.monotonic() - 60  # 60s ago

        # Second attempt: succeed
        mock_client_ok = AsyncMock()
        mock_client_ok.ping = AsyncMock(return_value=True)

        def _build_ok(*args, **kwargs):
            return mock_client_ok

        with (
            patch(
                "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
                return_value=mock_redis_settings,
            ),
            patch(
                "rhesis.backend.app.services.connector.redis_client.create_client",
                side_effect=_build_ok,
            ),
        ):
            await redis_manager.initialize()

        assert redis_manager._initialized
        assert redis_manager.is_available
        assert redis_manager._last_failed_at == 0  # cooldown reset

    @pytest.mark.asyncio
    async def test_no_retry_during_cooldown(self, redis_manager, mock_redis_settings):
        """Within cooldown window, initialize() must be a no-op."""
        # First attempt: fail
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_client.close = AsyncMock()

        with (
            patch(
                "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
                return_value=mock_redis_settings,
            ),
            patch(
                "rhesis.backend.app.services.connector.redis_client.create_client",
                return_value=mock_client,
            ),
        ):
            await redis_manager.initialize()

        failed_at = redis_manager._last_failed_at
        assert failed_at > 0

        # Second attempt immediately: should NOT retry (within cooldown)
        mock_client2 = AsyncMock()
        mock_client2.ping = AsyncMock(return_value=True)

        with (
            patch(
                "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
                return_value=mock_redis_settings,
            ),
            patch(
                "rhesis.backend.app.services.connector.redis_client.create_client",
                return_value=mock_client2,
            ),
        ):
            await redis_manager.initialize()

        # Still not initialized — cooldown prevented retry
        assert not redis_manager._initialized
        assert redis_manager._last_failed_at == failed_at  # unchanged

    @pytest.mark.asyncio
    async def test_is_available_false_until_connected(self, redis_manager, mock_redis_settings):
        """is_available must be False before successful connection."""
        assert not redis_manager.is_available

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=ConnectionError("down"))
        mock_client.close = AsyncMock()

        with (
            patch(
                "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
                return_value=mock_redis_settings,
            ),
            patch(
                "rhesis.backend.app.services.connector.redis_client.create_client",
                return_value=mock_client,
            ),
        ):
            await redis_manager.initialize()

        assert not redis_manager.is_available


class TestRedisConnectionResilience:
    """Verify the client is built so redis-py reconnects on its own (closes #1695)."""

    def test_dropped_connection_is_retried_not_raised(self):
        """A dropped connection must reconnect instead of surfacing to the caller.

        Asserted against the real client the code builds, so this catches an
        option being dropped or renamed rather than just "a builder was called".
        """
        from redis.exceptions import ConnectionError as RedisConnectionError
        from redis.exceptions import TimeoutError as RedisTimeoutError

        from rhesis.backend.app.services.connector.redis_client import create_client

        # create_client() opens no socket, so this is safe with no Redis server.
        connection = create_client("redis://localhost:6379/0").connection_pool.make_connection()

        # Zero retries or an empty retry_on_error is what made blpop raise instead of reconnect.
        assert connection.retry._retries > 0
        assert RedisConnectionError in connection.retry_on_error
        assert RedisTimeoutError in connection.retry_on_error
        assert RedisConnectionError in connection.retry._supported_errors

        # Keeps an idle pooled connection from being handed out already dead.
        assert connection.health_check_interval > 0
        assert connection.socket_keepalive is True

    def test_pool_blocks_instead_of_dropping_a_response(self):
        """An over-capacity burst must wait, never raise.

        The default ConnectionPool raises ConnectionError("Too many connections")
        the instant it is full, and redis-py acquires the connection *before* its
        retry wrapper so retry_on_error cannot save it. That lost SDK responses:
        the publish failed, the worker never woke, and the test reported a bogus
        120s endpoint timeout. Concurrency 15 lost a third of a 40-test run.
        """
        import redis.asyncio as redis_asyncio

        from rhesis.backend.app.services.connector.redis_client import create_client

        pool = create_client("redis://localhost:6379/0").connection_pool
        assert isinstance(pool, redis_asyncio.BlockingConnectionPool), (
            "must be a blocking pool; the default one discards responses under load"
        )
        assert pool.timeout is not None and pool.timeout > 0

    def test_pool_ceiling_clears_the_blocking_consumers(self):
        """The ceiling is a resource bound, not a throughput knob.

        It must stay above the connections pinned by blocking operations (the
        blpop RPC listener plus one heartbeat loop per connected SDK), or
        publishes queue behind them and starve. Measured: 3 starves completely
        with 3+ listeners; 16 stayed clean at every load tested.
        """
        from rhesis.backend.app.services.connector.redis_client import (
            _MAX_CONNECTIONS,
            create_client,
        )

        assert _MAX_CONNECTIONS >= 16, (
            f"{_MAX_CONNECTIONS} is too close to the number of blocking consumers; "
            "with tens of connected SDKs the pool saturates and publishes queue"
        )
        pool = create_client("redis://localhost:6379/0").connection_pool
        assert pool.max_connections == _MAX_CONNECTIONS
