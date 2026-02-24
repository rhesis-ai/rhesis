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


# Initialize limiter with default key function
limiter = Limiter(key_func=get_remote_address)
RATE_LIMIT_PER_DAY = "10000/day"
RATE_LIMIT_PER_MINUTE = "100/minute"

_rate_limit_per_day = parse(RATE_LIMIT_PER_DAY)
_rate_limit_per_minute = parse(RATE_LIMIT_PER_MINUTE)

RATE_LIMIT_ERROR_DETAIL = "Rate limit exceeded. Try again later."


async def check_rate_limit(
    request: Request,
    current_user: User = Depends(require_api_key),  # Authentication runs first
):
    """
    Rate limit dependency that runs after authentication.

    Enforces per-minute then daily limits. Ensures request.state.user_id
    is set before rate limiting is checked.
    """
    user_id = str(current_user.id)
    identifier = f"user:{user_id}"

    try:
        # Test both limits before incrementing either counter
        minute_ok = limiter._limiter.test(_rate_limit_per_minute, identifier)
        daily_ok = limiter._limiter.test(_rate_limit_per_day, identifier)

        if not minute_ok:
            logger.warning(f"Per-minute rate limit exceeded for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=RATE_LIMIT_ERROR_DETAIL,
            )
        if not daily_ok:
            logger.warning(f"Daily rate limit exceeded for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=RATE_LIMIT_ERROR_DETAIL,
            )

        # Both passed — increment both counters
        limiter._limiter.hit(_rate_limit_per_minute, identifier)
        limiter._limiter.hit(_rate_limit_per_day, identifier)

        logger.info(f"Rate limit check passed for user {user_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limiting error for user {user_id}: {str(e)}", exc_info=True)
        # Don't block request on rate limiter errors - fail open
        pass

    return current_user
