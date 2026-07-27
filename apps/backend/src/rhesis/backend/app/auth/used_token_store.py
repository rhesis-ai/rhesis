"""
Single-use token tracking for password reset, magic link, auth code,
and OIDC subject-token replay protection in token exchange.

Uses Redis SET NX with TTL to record that a token (by jti) has been used.
Once claimed, the same token cannot be used again until the TTL elapses.

Also provides server-side storage for opaque auth codes: the login
redirect hands the browser a random code, and the session/refresh tokens
it references live only here — never inside the code (and therefore never
in URLs, browser history, or access logs).
"""

import hashlib
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


REDIS_KEY_PREFIX = "used_jti:"
AUTH_CODE_KEY_PREFIX = "auth_code:"


class TokenStoreUnavailableError(Exception):
    """Raised when the token store (Redis) is not available."""

    pass


def _build_replay_key(jti: str, namespace: Optional[str]) -> str:
    """Compose the Redis key for a single-use jti claim.

    *namespace* MUST be supplied for any token whose ``jti`` value
    space is shared with an external issuer (e.g. an OIDC IdP). Two
    different IdPs can legitimately mint the same ``jti`` value
    (Keycloak uses UUIDs but the spec only RECOMMENDS uniqueness, and
    smaller IdPs use sequential integers); without a namespace,
    the second issuer's legitimate first-use would be rejected as a
    replay of the first issuer's already-claimed token.

    For Rhesis-internal tokens (auth codes, password reset, magic
    link) the jti space is uniformly UUIDv4 from our own minter and
    does not collide. Those callers may pass ``namespace=None``.

    The namespace is hashed (sha256, first 16 hex chars) so a long
    issuer URL does not blow up the Redis key length, and so the
    on-disk Redis layout doesn't reveal which IdPs we integrate with
    just by listing keys.
    """
    if namespace is None:
        return f"{REDIS_KEY_PREFIX}{jti}"
    ns_hash = hashlib.sha256(namespace.encode("utf-8")).hexdigest()[:16]
    return f"{REDIS_KEY_PREFIX}{ns_hash}:{jti}"


async def claim_token_jti(
    jti: str,
    ttl_seconds: int,
    *,
    namespace: Optional[str] = None,
) -> bool:
    """
    Try to claim a token jti as used (single-use enforcement).

    Uses Redis SET key NX EX: only sets the key if it does not exist.
    Returns True if we claimed it (first use), False if already used.
    Raises TokenStoreUnavailableError if Redis is not available.

    Args:
        jti: The JWT ID claim from the token.
        ttl_seconds: TTL for the key (should match token expiry).
        namespace: Optional disambiguator for jti values from external
            issuers. Pass the issuer URL when claiming an OIDC subject
            token's jti so two IdPs that legitimately mint the same
            jti value cannot DoS each other. Internal Rhesis tokens
            (auth codes, password reset, magic link) leave this None
            because the jti space is uniformly our own UUIDv4.

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
        key = _build_replay_key(jti, namespace)
        # SET key "1" NX EX ttl_seconds -> True if key was set, False if exists
        was_set = await redis_manager.client.set(key, "1", nx=True, ex=ttl_seconds)
        return bool(was_set)
    except TokenStoreUnavailableError:
        raise
    except Exception as e:
        logger.warning("Failed to claim token jti: %s", type(e).__name__)
        raise TokenStoreUnavailableError("Token store temporarily unavailable")


def _auth_code_key(code: str) -> str:
    """Key the stored tokens by a hash of the code, not the code itself.

    The code is a bearer secret while it lives; hashing means a Redis
    dump/monitor never exposes directly usable codes.
    """
    return f"{AUTH_CODE_KEY_PREFIX}{hashlib.sha256(code.encode('utf-8')).hexdigest()}"


async def store_auth_code_tokens(
    code: str,
    session_token: str,
    refresh_token: Optional[str],
    ttl_seconds: int,
) -> None:
    """Store the token pair referenced by an opaque auth code.

    Raises:
        TokenStoreUnavailableError: If Redis is not available. Callers fall
            back to the legacy JWT-embedded code so logins keep working.
    """
    from rhesis.backend.app.services.connector.redis_client import (
        redis_manager,
    )

    if not redis_manager.is_available:
        raise TokenStoreUnavailableError("Token store temporarily unavailable")

    payload: Dict[str, str] = {"session_token": session_token}
    if refresh_token:
        payload["refresh_token"] = refresh_token

    try:
        await redis_manager.client.set(_auth_code_key(code), json.dumps(payload), ex=ttl_seconds)
    except Exception as e:
        logger.warning("Failed to store auth code tokens: %s", type(e).__name__)
        raise TokenStoreUnavailableError("Token store temporarily unavailable")


async def consume_auth_code_tokens(code: str) -> Optional[Dict[str, str]]:
    """Atomically fetch-and-delete the tokens for an opaque auth code.

    GETDEL makes single-use inherent: a second exchange of the same code
    finds nothing. Returns None when the code is unknown, expired, or
    already used.

    Raises:
        TokenStoreUnavailableError: If Redis is not available (the tokens
            may exist but cannot be reached — distinct from "invalid code").
    """
    from rhesis.backend.app.services.connector.redis_client import (
        redis_manager,
    )

    if not redis_manager.is_available:
        raise TokenStoreUnavailableError("Token store temporarily unavailable")

    try:
        raw = await redis_manager.client.getdel(_auth_code_key(code))
    except Exception as e:
        logger.warning("Failed to consume auth code: %s", type(e).__name__)
        raise TokenStoreUnavailableError("Token store temporarily unavailable")

    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("Auth code payload was not valid JSON; treating as invalid")
        return None
