"""Session management utilities for authentication flows."""

from fastapi import Request


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
