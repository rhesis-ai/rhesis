"""
Authentication module for Polyphemus service.
Provides API key authentication using Rhesis API tokens (format: rh-*).
Reuses authentication utilities from rhesis.backend for consistency.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from rhesis.backend.app.auth.token_validation import validate_token
from rhesis.backend.app.crud import get_token_by_value, get_user_by_id
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User

logger = logging.getLogger("rhesis-polyphemus")

bearer_scheme = HTTPBearer(auto_error=False)


async def require_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    """
    FastAPI dependency to require and validate API key authentication.

    Accepts Bearer tokens in the format: rh-* (Rhesis API tokens).
    Uses backend utilities from rhesis.backend.app for consistent token validation.

    Sets user_id in request state for rate limiting identification.

    Args:
        request: FastAPI Request object
        credentials: HTTP Authorization credentials from the request header

    Returns:
        User: The authenticated user object

    Raises:
        HTTPException: 401 if token is invalid, missing, or not found in database
                      403 if user account is inactive
    """
    if not credentials:
        logger.warning("API request received without authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    token_value = credentials.credentials

    try:
        with get_db() as db:
            # Use backend's validate_token utility from token_validation module
            # This handles format validation (rh-*), existence check, and expiration
            is_valid, error_message = validate_token(token_value, update_usage=True, db=db)

            if not is_valid:
                logger.warning(f"Token validation failed: {error_message}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=error_message or "Invalid or revoked token",
                )

            # Retrieve the token and get associated user using backend CRUD utilities
            token = get_token_by_value(db, token_value)
            user = get_user_by_id(db, token.user_id) if token else None

            if not user:
                logger.warning(f"User not found for token: {token_value[:10]}...")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                )

            # Verify user account is active
            if not user.is_active:
                logger.warning(f"Attempted access with inactive user: {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

            # Set user_id in request state for rate limiting
            request.state.user_id = str(user.id)

            logger.info(f"API key authenticated successfully for user: {user.email}")
            return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during API key validation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error",
        )
