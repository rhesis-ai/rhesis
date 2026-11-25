"""Re-check that the credential behind an open WebSocket is still valid.

A socket authenticates once, at connect, with a browser/JWT session, a
short-lived WS token, or an ``rh-*`` API token. The membership re-check closes a
socket once its user leaves the organization; this adds the matching check for
the *credential*, so a logged-out session or a revoked API token drops its open
socket instead of living on until the client happens to disconnect.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import anyio

from rhesis.backend.app.auth.session_invalidation import is_session_revoked

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SocketCredential:
    """What a socket authenticated with, enough to re-check it on a timer.

    At most one identifying field is set:

    - ``session_issued_at``: a browser/JWT session, or a WS token minted from
      one. Logout and password change write a per-user "revoked before" mark in
      Redis; a session issued earlier than the mark is revoked.
    - ``api_token_value``: an ``rh-*`` API token, revoked when its row is deleted
      or it expires.

    Stateless M2M / ``azp`` JWTs carry neither; they are bounded by their own
    short expiry and treated as always-current here.
    """

    user_id: str
    session_issued_at: Optional[int] = None
    api_token_value: Optional[str] = None


def credential_from_bearer(token: str, user_id: str, is_session: bool) -> SocketCredential:
    """Describe the credential a Bearer-authenticated socket opened with.

    An ``rh-*`` token is re-checked by its DB row; a session JWT by its issue
    time against the per-user logout mark. An EE M2M (``azp``) JWT is a token that
    carries neither and is bounded by its own short expiry.
    """
    if token.startswith("rh-"):
        return SocketCredential(user_id=user_id, api_token_value=token)
    if is_session:
        try:
            from rhesis.backend.app.auth.token_utils import verify_jwt_token
            from rhesis.backend.app.auth.user_utils import get_secret_key

            payload = verify_jwt_token(token, get_secret_key())
            return SocketCredential(user_id=user_id, session_issued_at=int(payload["iat"]))
        except Exception:
            logger.debug("Could not read JWT iat for WebSocket credential re-check", exc_info=True)
    return SocketCredential(user_id=user_id)


def _api_token_valid(token_value: str) -> bool:
    """Whether an ``rh-*`` token still exists and has not expired. One DB read."""
    from rhesis.backend.app.auth.token_validation import validate_token
    from rhesis.backend.app.database import get_db

    with get_db() as db:
        is_valid, _ = validate_token(token_value, update_usage=False, db=db)
        return is_valid


async def credential_is_current(credential: SocketCredential) -> bool:
    """True while the credential that opened the socket is still valid.

    A failed lookup counts as current, matching the membership re-check: a Redis
    or database hiccup must not drop every open socket, and the next interval
    re-checks. A positive revocation signal (logout mark, missing token) still
    closes the socket.
    """
    try:
        if credential.session_issued_at is not None:
            return not await is_session_revoked(credential.user_id, credential.session_issued_at)
        if credential.api_token_value is not None:
            return await anyio.to_thread.run_sync(_api_token_valid, credential.api_token_value)
        # No re-checkable credential (e.g. stateless M2M JWT): bounded by its own expiry.
        return True
    except Exception as e:
        logger.warning(
            "WebSocket credential re-check failed for user %s: %s", credential.user_id, e
        )
        return True
