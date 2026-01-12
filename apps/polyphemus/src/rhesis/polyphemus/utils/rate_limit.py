"""
Rate limiting utilities for Polyphemus service.
Provides user-based rate limiting using slowapi library.
Reuses authentication and rate limiting patterns from rhesis.backend.
"""

import logging

from fastapi import Depends, HTTPException, Request, status
from limits import parse
from slowapi import Limiter
from slowapi.util import get_remote_address

from rhesis.backend.app.models.user import User
from rhesis.polyphemus.services.auth import require_api_key

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

# Parse the rate limit string into a RateLimitItem for manual checking
_rate_limit_item = parse(RATE_LIMIT_AUTHENTICATED)


async def check_rate_limit(
    request: Request,
    current_user: User = Depends(require_api_key),  # Authentication runs first
):
    """
    Rate limit dependency that runs after authentication.

    This ensures request.state.user_id is set before rate limiting is checked.

    Users with email addresses ending in @rhesis.ai are exempt from rate limiting.
    """
    user_id = str(current_user.id)

    # Skip rate limiting for users with @rhesis.ai email addresses
    if current_user.email.endswith("@rhesis.ai"):
        logger.info(f"Rate limit bypassed for @rhesis.ai user: {current_user.email}")
        return current_user

    identifier = f"user:{user_id}"

    # Manually perform rate limit check using slowapi's internal limiter
    try:
        # Use the limiter's internal _limiter.hit() method
        # Returns True if allowed, False if rate limit would be exceeded
        allowed = limiter._limiter.hit(_rate_limit_item, identifier)

        if not allowed:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
            )

        logger.info(f"Rate limit check passed for user {user_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limiting error for user {user_id}: {str(e)}", exc_info=True)
        # Don't block request on rate limiter errors - fail open
        pass

    return current_user
