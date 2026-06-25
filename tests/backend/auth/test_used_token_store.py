"""
Unit tests for single-use token store (claim_token_jti).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.auth.used_token_store import (
    REDIS_KEY_PREFIX,
    TokenStoreUnavailableError,
    _build_replay_key,
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

    @pytest.mark.asyncio
    async def test_claim_namespace_changes_redis_key(self):
        """Same jti under different namespaces hits distinct Redis keys.

        Regression coverage for the cross-IdP collision fix: two OIDC
        issuers can legitimately mint identical jti values, and without
        a namespace the second issuer's first-use is rejected as a
        replay of the first issuer's already-claimed token.
        """
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch(_REDIS_MGR) as mock_mgr:
            mock_mgr.is_available = True
            mock_mgr.client = mock_redis

            await claim_token_jti(
                "shared-jti", ttl_seconds=300, namespace="https://idp-a/"
            )
            await claim_token_jti(
                "shared-jti", ttl_seconds=300, namespace="https://idp-b/"
            )
            await claim_token_jti("shared-jti", ttl_seconds=300)  # default ns

        assert mock_redis.set.call_count == 3
        keys = [call.args[0] for call in mock_redis.set.call_args_list]
        assert len(set(keys)) == 3, f"expected 3 distinct keys, got {keys}"


@pytest.mark.unit
class TestBuildReplayKey:
    """Tests for the _build_replay_key helper."""

    def test_no_namespace_returns_legacy_shape(self):
        """Internal callers (auth code, password reset) keep the legacy key shape."""
        key = _build_replay_key("abc-123", None)
        assert key == f"{REDIS_KEY_PREFIX}abc-123"

    def test_namespace_is_hashed_not_raw(self):
        """Namespaces are sha256-prefixed so issuer URLs don't leak via Redis keys."""
        key = _build_replay_key("abc", "https://example.com/realms/x")
        assert "https://" not in key
        assert "example" not in key
        assert key.startswith(f"{REDIS_KEY_PREFIX}")
        assert key.endswith(":abc")

    def test_distinct_namespaces_yield_distinct_keys(self):
        """Two issuers minting the same jti must not share a Redis key."""
        a = _build_replay_key("jti", "https://idp-a/")
        b = _build_replay_key("jti", "https://idp-b/")
        assert a != b
