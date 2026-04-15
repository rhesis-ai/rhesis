"""Session management utilities for authentication flows."""

from fastapi import Request


def regenerate_session(request: Request, new_data: dict) -> None:
    """Atomically clear and repopulate the session after authentication.

    Prevents session fixation by ensuring the pre-authentication session ID
    is discarded. Starlette's SessionMiddleware issues a new cookie when
    the session dict changes.

    Args:
        request: The current FastAPI/Starlette request.
        new_data: The key-value pairs for the new authenticated session
                  (e.g., {"user_id": user.id}).
    """
    request.session.clear()
    request.session.update(new_data)
