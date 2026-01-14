import base64
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import HTTPException, status
from jose import JWTError, jwt

from rhesis.backend.app.auth.constants import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM
from rhesis.backend.app.models.user import User
from rhesis.backend.logging import logger

# Service delegation token expiration time
SERVICE_DELEGATION_EXPIRE_MINUTES = 5


def get_secret_key() -> str:
    """Get JWT secret key from environment"""
    secret_key = os.getenv("JWT_SECRET_KEY")
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET_KEY not configured",
        )
    return secret_key


def create_session_token(user: User) -> str:
    """Create a new session token for a user"""
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    # Convert UUID to string for JSON serialization
    organization_id = str(user.organization_id) if user.organization_id else None

    to_encode = {
        "sub": str(user.id),  # Convert UUID to string
        "iat": now,
        "exp": expire,
        "type": "session",
        "user": {
            "id": str(user.id),  # Convert UUID to string
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "is_superuser": user.is_superuser,
            "organization_id": organization_id,  # Already converted to string or None
        },
    }

    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def create_service_delegation_token(
    user: User,
    target_service: str,
    expires_minutes: int = SERVICE_DELEGATION_EXPIRE_MINUTES,
) -> str:
    """
    Create short-lived JWT token for service-to-service delegation.

    Args:
        user: User on whose behalf the request is made
        target_service: Target service name (e.g., "polyphemus")
        expires_minutes: Token lifetime (default: 5 minutes)

    Returns:
        JWT token string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)

    payload = {
        "type": "service_delegation",
        "target_service": target_service,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "organization_id": str(user.organization_id) if user.organization_id else None,
        },
        "iat": now,
        "exp": expire,
        "nbf": now,
    }

    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def verify_jwt_token(token: str, secret_key: str, algorithm: str = ALGORITHM) -> Dict[str, Any]:
    """
    Verify and decode a JWT token with explicit expiration checks.
    Returns the decoded payload if valid, raises JWTError if not.
    """
    try:
        # Verify the JWT token with explicit expiration check
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options={
                "verify_exp": True,  # Explicitly verify expiration
                "verify_iat": True,  # Verify issued at time
                "require_exp": True,  # Require expiration time
                "require_iat": True,  # Require issued at time
            },
        )

        # Check if it's a session token
        if payload.get("type") != "session":
            logger.warning(f"Invalid token type: {payload.get('type')}")
            raise JWTError("Invalid token type")

        # Log successful verification
        if "user" in payload:
            logger.debug(f"JWT token validated for user: {payload['user'].get('email')}")
            logger.debug(
                f"Token expiration: {datetime.fromtimestamp(payload['exp'], tz=timezone.utc)}"
            )

        return payload

    except JWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        if "Expired token" in str(e):
            logger.warning("JWT token has expired")
        raise


def generate_api_token() -> str:
    """Generate a secure API token in OpenAI-style format"""
    while True:
        token_bytes = secrets.token_bytes(32)
        token_b64 = base64.urlsafe_b64encode(token_bytes).decode("utf-8").rstrip("=")
        if "-" not in token_b64:
            return f"rh-{token_b64}"
