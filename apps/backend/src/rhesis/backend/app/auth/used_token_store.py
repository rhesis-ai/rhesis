"""
Single-use token tracking for password reset and magic link.

Uses Redis SET NX with TTL to record that a token (by jti) has been used.
Once claimed, the same token cannot be used again.
"""

from rhesis.backend.logging import logger

REDIS_KEY_PREFIX = "used_jti:"


class TokenStoreUnavailableError(Exception):
    """Raised when the token store (Redis) is not available."""

    pass


async def claim_token_jti(jti: str, ttl_seconds: int) -> bool:
    """
    Try to claim a token jti as used (single-use enforcement).

    Uses Redis SET key NX EX: only sets the key if it does not exist.
    Returns True if we claimed it (first use), False if already used.
    Raises TokenStoreUnavailableError if Redis is not available.

    Args:
        jti: The JWT ID claim from the token.
        ttl_seconds: TTL for the key (should match token expiry).

    Returns:
        True if token was just claimed (first use), False if already used.

    Raises:
        TokenStoreUnavailableError: If Redis is not available.
    """
    from rhesis.backend.app.services.connector.redis_client import (
        redis_manager,
    )

    if not redis_manager.is_available:
        logger.warning("Redis not available; cannot enforce single-use token")
        raise TokenStoreUnavailableError("Token store temporarily unavailable")

    try:
        key = f"{REDIS_KEY_PREFIX}{jti}"
        # SET key "1" NX EX ttl_seconds -> True if key was set, False if exists
        was_set = await redis_manager.client.set(key, "1", nx=True, ex=ttl_seconds)
        return bool(was_set)
    except TokenStoreUnavailableError:
        raise
    except Exception as e:
        logger.warning("Failed to claim token jti: %s", e)
        raise TokenStoreUnavailableError("Token store temporarily unavailable")
