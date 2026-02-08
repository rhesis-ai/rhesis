"""
Rate limiting utilities for the application.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Create limiter instance
limiter = Limiter(key_func=get_remote_address, default_limits=["1000/day", "100/hour"])


def get_user_identifier(request: Request) -> str:
    """
    Get a unique identifier for rate limiting.
    Uses user ID if available, otherwise falls back to IP address.
    """
    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fall back to IP address
    return get_remote_address(request)


# Create user-aware limiter
user_limiter = Limiter(key_func=get_user_identifier, default_limits=["1000/day", "100/hour"])

# Rate limits for different operations
INVITATION_RATE_LIMIT = "10/hour"  # Max 10 invitations per hour per user
BULK_INVITATION_RATE_LIMIT = "3/hour"  # Max 3 bulk invitations per hour per user

# Auth endpoint rate limits (per IP, no auth yet)
AUTH_FORGOT_PASSWORD_LIMIT = "5/hour"
AUTH_RESEND_VERIFICATION_LIMIT = "5/hour"
AUTH_MAGIC_LINK_LIMIT = "5/hour"
AUTH_LOGIN_EMAIL_LIMIT = "20/hour"
AUTH_REGISTER_LIMIT = "10/hour"
