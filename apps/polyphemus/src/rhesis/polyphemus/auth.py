"""
Authentication module for Polyphemus service.
Provides API key authentication using Rhesis API tokens (format: rh-*).
Reuses authentication utilities from rhesis.backend for consistency.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from rhesis.backend.app.auth.token_validation import validate_token
from rhesis.backend.app.crud import get_token_by_value, get_user_by_id
from rhesis.backend.app.models.user import User

from .database import get_db

logger = logging.getLogger("rhesis-polyphemus")

bearer_scheme = HTTPBearer(auto_error=False)


async def require_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    """
    FastAPI dependency to require and validate API key authentication.

    Accepts Bearer tokens in the format: rh-*

    Args:
        credentials: HTTP Authorization credentials from the request header

    Returns:
        User: The authenticated user object

    Raises:
        HTTPException: 401 if token is invalid, missing, or not found in database
    """
    # Check if credentials are provided
    if not credentials:
        logger.warning("API request received without authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    token_value = credentials.credentials

    # Validate token format (must start with rh-)
    if not token_value.startswith("rh-"):
        logger.warning(f"Invalid token format: {token_value[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format. Token must start with 'rh-'",
        )

    # Validate token against database
    try:
        with get_db() as db:
            # Retrieve the token object from database
            token = get_token_by_value(db, token_value)

            if not token:
                logger.warning(f"Token not found in database: {token_value[:10]}...")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token not found",
                )

            # Validate token (exists, not revoked, not expired)
            # Passing token object directly to avoid second DB call
            is_valid, error_message = validate_token(token, db=db)

            if not is_valid:
                logger.warning(f"Token validation failed: {error_message}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=error_message or "Invalid or revoked token",
                )

            # Get the associated user
            user = get_user_by_id(db, token.user_id)

            if not user:
                logger.warning(f"User not found for token: {token_value[:10]}...")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                )

            if not user.is_active:
                logger.warning(f"Attempted access with inactive user: {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )

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
