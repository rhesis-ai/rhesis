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

import asyncio
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

        with patch(
            "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
            return_value=mock_redis_settings,
        ), patch(
            "rhesis.backend.app.services.connector.redis_client.redis.from_url",
            return_value=mock_client,
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

        async def _from_url_fail(*args, **kwargs):
            return mock_client_fail

        with patch(
            "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
            return_value=mock_redis_settings,
        ), patch(
            "rhesis.backend.app.services.connector.redis_client.redis.from_url",
            side_effect=_from_url_fail,
        ):
            await redis_manager.initialize()
        assert not redis_manager._initialized

        # Simulate cooldown expiry
        redis_manager._last_failed_at = time.monotonic() - 60  # 60s ago

        # Second attempt: succeed
        mock_client_ok = AsyncMock()
        mock_client_ok.ping = AsyncMock(return_value=True)

        async def _from_url_ok(*args, **kwargs):
            return mock_client_ok

        with patch(
            "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
            return_value=mock_redis_settings,
        ), patch(
            "rhesis.backend.app.services.connector.redis_client.redis.from_url",
            side_effect=_from_url_ok,
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

        with patch(
            "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
            return_value=mock_redis_settings,
        ), patch(
            "rhesis.backend.app.services.connector.redis_client.redis.from_url",
            return_value=mock_client,
        ):
            await redis_manager.initialize()

        failed_at = redis_manager._last_failed_at
        assert failed_at > 0

        # Second attempt immediately: should NOT retry (within cooldown)
        mock_client2 = AsyncMock()
        mock_client2.ping = AsyncMock(return_value=True)

        with patch(
            "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
            return_value=mock_redis_settings,
        ), patch(
            "rhesis.backend.app.services.connector.redis_client.redis.from_url",
            return_value=mock_client2,
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

        with patch(
            "rhesis.backend.app.services.connector.redis_client.get_redis_settings",
            return_value=mock_redis_settings,
        ), patch(
            "rhesis.backend.app.services.connector.redis_client.redis.from_url",
            return_value=mock_client,
        ):
            await redis_manager.initialize()

        assert not redis_manager.is_available
