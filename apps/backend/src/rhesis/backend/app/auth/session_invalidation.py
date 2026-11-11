"""Revoke a user's session JWTs on logout and password change.

JWTs are stateless, so revocation is a per-user "revoked before" timestamp in
Redis: a session JWT whose ``iat`` is older than the mark is rejected. Redis is
shared by every backend pod, so the mark applies everywhere at once, and the key
expires once every JWT it could match has expired on its own.

When Redis is unreachable the check fails open (logged): the session JWT then
lives out its short TTL, while refresh tokens are still revoked in the database.
"""

import logging
import time
from typing import Optional

import anyio

from rhesis.backend.app.config.settings import get_auth_settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "session_revoked_before:"

# Issue time assumed for a cookie session that predates issue times: it was
# issued no later than this, and any revocation written from now on is newer.
PROCESS_STARTED_AT = int(time.time())

# Upper bound on the per-request lookup, so a hung Redis can't stall every request.
LOOKUP_TIMEOUT_SECONDS = 0.25

# Clock skew allowance on top of the session JWT lifetime.
_TTL_MARGIN_SECONDS = 60

_WARN_INTERVAL_SECONDS = 60
_last_warned_at = 0.0


def _key(user_id: str) -> str:
    return f"{KEY_PREFIX}{user_id}"


def _ttl_seconds() -> int:
    return get_auth_settings().jwt_access_token_expire_minutes * 60 + _TTL_MARGIN_SECONDS


def _warn_unavailable(action: str, error: Optional[BaseException] = None) -> None:
    """Log at most once a minute: this path runs on every request while Redis is down."""
    global _last_warned_at
    now = time.monotonic()
    if now - _last_warned_at < _WARN_INTERVAL_SECONDS:
        return
    _last_warned_at = now
    reason = type(error).__name__ if error else "Redis unavailable"
    logger.warning("Session revocation %s skipped (%s); failing open", action, reason)


async def _client(*, connect: bool):
    """The shared client, or None. Only ``connect=True`` may try to (re)connect."""
    from rhesis.backend.app.services.connector.redis_client import redis_manager

    if connect:
        # No-op once connected; throttled internally after a failure.
        await redis_manager.initialize()
    return redis_manager.client if redis_manager.is_available else None


async def invalidate_user_sessions(user_id: str) -> None:
    """Reject every session JWT issued to ``user_id`` before now.

    Second precision, like JWT ``iat``: a token minted later in the same second
    (the fresh token after a password change) stays valid.
    """
    try:
        client = await _client(connect=True)
        if client is None:
            _warn_unavailable("write")
            return
        await client.set(_key(user_id), str(int(time.time())), ex=_ttl_seconds())
        logger.info("Revoked session tokens issued before now for user %s", user_id)
    except Exception as e:
        _warn_unavailable("write", e)


async def is_session_revoked(user_id: str, issued_at: int) -> bool:
    """Whether a session JWT with ``iat`` = ``issued_at`` was revoked. One Redis GET.

    Never connects: a connect attempt has no tight timeout, so it stays off the
    per-request path. Startup, logins and logouts reconnect the shared client.
    """
    try:
        client = await _client(connect=False)
        if client is None:
            _warn_unavailable("check")
            return False
        with anyio.fail_after(LOOKUP_TIMEOUT_SECONDS):
            revoked_before = await client.get(_key(user_id))
        return revoked_before is not None and int(issued_at) < int(revoked_before)
    except Exception as e:
        _warn_unavailable("check", e)
        return False
