"""
Rate limiting utilities for Polyphemus service.
Provides user-based rate limiting using slowapi library.
Reuses authentication and rate limiting patterns from rhesis.backend.
"""

import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger("rhesis-polyphemus")


def get_rate_limit_identifier(request: Request) -> str:
    """
    Get a unique identifier for rate limiting.

    For authenticated requests (with user_id set by auth dependency):
      Returns: "user:{user_id}"
    For unauthenticated requests:
      Returns: "ip:{ip_address}"

    Args:
        request: FastAPI Request object

    Returns:
        str: Unique rate limit identifier
    """
    # Try to get user ID from request state (set by require_api_key dependency)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        logger.debug(f"Rate limiting by user: {user_id}")
        return f"user:{user_id}"

    # Fall back to IP address for unauthenticated requests
    ip = get_remote_address(request)
    logger.debug(f"Rate limiting by IP: {ip}")
    return f"ip:{ip}"


# Initialize limiter with custom key function
limiter = Limiter(key_func=get_rate_limit_identifier)

# Rate limits for different tiers
RATE_LIMIT_AUTHENTICATED = "100/day"  # 100 requests per day per authenticated user
