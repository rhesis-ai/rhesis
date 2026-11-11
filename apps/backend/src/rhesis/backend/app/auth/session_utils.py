"""Session management utilities for authentication flows."""

import time

from fastapi import Request

SESSION_USER_KEY = "user_id"
SESSION_ISSUED_AT_KEY = "iat"


def set_session_user(request: Request, user_id: str) -> None:
    """Sign ``user_id`` in on the cookie session, stamped for revocation checks."""
    request.session[SESSION_USER_KEY] = user_id
    request.session[SESSION_ISSUED_AT_KEY] = int(time.time())


def regenerate_session(request: Request, new_data: dict) -> None:
    """Clear pre-authentication session data and populate with new auth state.

    Starlette's SessionMiddleware uses a signed client-side cookie — there is
    no server-side session ID to rotate.  Clearing the cookie payload and
    rewriting it with freshly-authenticated data achieves the practical goal:
    any state accumulated before authentication (e.g. a partially-filled form
    or a CSRF nonce) is dropped and cannot be re-used by the authenticated
    session.

    Args:
        request: The current FastAPI/Starlette request.
        new_data: The key-value pairs for the new authenticated session
                  (e.g., {"user_id": user.id}).
    """
    request.session.clear()
    request.session.update(new_data)
    if SESSION_USER_KEY in new_data:
        request.session[SESSION_ISSUED_AT_KEY] = int(time.time())
