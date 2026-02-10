"""
Unit tests for single-use token store (claim_token_jti).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.auth.used_token_store import (
    TokenStoreUnavailableError,
    claim_token_jti,
)

# redis_manager is imported inside claim_token_jti via deferred import,
# so we patch it at its source module.
_REDIS_MGR = "rhesis.backend.app.services.connector.redis_client.redis_manager"


@pytest.mark.unit
class TestClaimTokenJti:
    """Tests for claim_token_jti."""

    @pytest.mark.asyncio
    async def test_claim_returns_true_on_first_use(self):
        """First claim for a jti returns True."""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch(_REDIS_MGR) as mock_mgr:
            mock_mgr.is_available = True
            mock_mgr.client = mock_redis

            result = await claim_token_jti("jti-123", ttl_seconds=3600)

        assert result is True
        mock_redis.set.assert_called_once()
        call_kw = mock_redis.set.call_args[1]
        assert call_kw.get("nx") is True
        assert call_kw.get("ex") == 3600

    @pytest.mark.asyncio
    async def test_claim_returns_false_when_already_used(self):
        """Second claim for same jti returns False (already used)."""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=False)

        with patch(_REDIS_MGR) as mock_mgr:
            mock_mgr.is_available = True
            mock_mgr.client = mock_redis

            result = await claim_token_jti("jti-used", ttl_seconds=900)

        assert result is False

    @pytest.mark.asyncio
    async def test_claim_raises_when_redis_unavailable(self):
        """When Redis is not available, raises TokenStoreUnavailableError."""
        with patch(_REDIS_MGR) as mock_mgr:
            mock_mgr.is_available = False

            with pytest.raises(TokenStoreUnavailableError) as exc_info:
                await claim_token_jti("jti-1", ttl_seconds=60)

        assert "temporarily unavailable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_claim_raises_on_redis_error(self):
        """On Redis client error, raises TokenStoreUnavailableError."""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(side_effect=ConnectionError("redis down"))

        with patch(_REDIS_MGR) as mock_mgr:
            mock_mgr.is_available = True
            mock_mgr.client = mock_redis

            with pytest.raises(TokenStoreUnavailableError):
                await claim_token_jti("jti-1", ttl_seconds=60)
