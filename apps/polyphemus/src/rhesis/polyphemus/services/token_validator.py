"""JWT token validation for service delegation."""

import logging
import os

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from rhesis.backend.app.crud import get_user_by_id
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User

logger = logging.getLogger("rhesis-polyphemus")

ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    """Get JWT secret key from environment."""
    secret_key = os.getenv("JWT_SECRET_KEY")
    if not secret_key:
        raise ValueError("JWT_SECRET_KEY not configured")
    return secret_key


def validate_delegation_token(request: Request, token: str) -> User:
    """
    Validate JWT delegation token from backend/worker.

    Returns User if valid, raises HTTPException otherwise.
    """
    try:
        secret_key = get_jwt_secret()

        # Decode JWT
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[ALGORITHM],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "require_exp": True,
                "require_iat": True,
            },
        )

        # Validate type
        if payload.get("type") != "service_delegation":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        # Validate target service
        if payload.get("target_service") != "polyphemus":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token not valid for this service",
            )

        # Get user
        user_info = payload.get("user", {})
        user_id = user_info.get("id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user information",
            )

        # Fetch from database
        with get_db() as db:
            user = get_user_by_id(db, user_id)

            if not user or not user.is_active or not user.is_verified:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User not found or inactive",
                )

            # Set for rate limiting
            request.state.user_id = str(user.id)

            logger.info(f"Delegation token validated: {user.email}")
            return user

    except JWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired delegation token",
        )
