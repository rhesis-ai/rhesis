import base64
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from rhesis.backend.app.crud import get_token_by_value, get_user_by_id
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.logging import logger

# Constants
bearer_scheme = HTTPBearer(auto_error=False)
UNAUTHORIZED_MESSAGE = "Authentication required"
ALGORITHM = "HS256"


class AuthenticationMethod:
    SESSION = "session"
    BEARER = "bearer"
    JWT = "jwt"


def get_secret_key() -> str:
    """Get JWT secret key from environment"""
    secret_key = os.getenv("JWT_SECRET_KEY")
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET_KEY not configured",
        )
    return secret_key


async def get_current_user(request: Request) -> Optional[User]:
    """
    Get current user from session using org-aware database session.

    Uses a simple session to get user and organization_id, then returns the user
    only if they have an organization_id. The actual database operations that
    need tenant context should pass organization_id and user_id directly to CRUD operations.
    """
    if "user_id" not in request.session:
        return None

    user_id = request.session.get("user_id")

    # Get the user with a basic session - no organization context needed for user lookup
    from rhesis.backend.app.database import get_db

    with get_db() as db:
        user = get_user_by_id(db, user_id)

    # User must have an organization_id to proceed
    if not user or not user.organization_id:
        return None

    return user


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


async def get_user_from_jwt(
    token: str, db: Session, secret_key: str, algorithm: str = ALGORITHM
) -> Optional[User]:
    """Get user from JWT token"""
    try:
        payload = verify_jwt_token(token, secret_key, algorithm)
        user_info = payload.get("user", {})
        user_id = user_info.get("id")

        if user_id:
            return get_user_by_id(db, user_id)

    except JWTError:
        return None

    return None


def update_token_usage(db: Session, token) -> None:
    """Update the last_used_at timestamp for a token."""
    try:
        token.last_used_at = datetime.now(timezone.utc)
        db.add(token)
        # Transaction commit/rollback is handled by the session context manager
    except Exception as e:
        logger.error(f"Failed to update token last_used_at: {str(e)}")
        # Transaction rollback is handled by the session context manager


def validate_token(
    token_or_value, update_usage: bool = True, db: Session = None
) -> tuple[bool, Optional[str]]:
    """
    Validate token format, existence, and expiration. Optionally update usage.
    Returns (is_valid, error_message)
    """
    # Handle both token value strings and token objects
    if isinstance(token_or_value, str):
        if not token_or_value.startswith("rh-"):
            return False, "Invalid token format. Token must start with 'rh-'"
        if not db:
            return False, "Database session required to validate token value"
        token = get_token_by_value(db, token_or_value)
    else:
        token = token_or_value

    if not token:
        return False, "Invalid or revoked token"

    # Check expiration only if expires_at is not None
    if token.expires_at:
        # Make sure token.expires_at is timezone-aware
        token_expiry = (
            token.expires_at
            if token.expires_at.tzinfo
            else token.expires_at.replace(tzinfo=timezone.utc)
        )
        now = datetime.now(timezone.utc)

        if token_expiry <= now:
            return False, "Token has expired"

    if update_usage and db:
        update_token_usage(db, token)

    return True, None


async def get_user_from_jwt(token: str, secret_key: str) -> Optional[User]:
    """
    Get user from JWT token using simple database session.

    Uses a simple session to get user and organization_id, then returns the user
    only if they have an organization_id. The actual database operations that
    need tenant context should pass organization_id and user_id directly to CRUD operations.
    """
    try:
        payload = verify_jwt_token(token, secret_key)
        user_info = payload.get("user", {})
        user_id = user_info.get("id")

        if user_id:
            # Get the user with a basic session - no organization context needed for user lookup
            from rhesis.backend.app.database import get_db

            with get_db() as db:
                user = get_user_by_id(db, user_id)

            # User must have an organization_id to proceed
            if not user or not user.organization_id:
                return None

            return user

    except Exception:
        return None

    return None


async def get_authenticated_user_with_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    secret_key: Optional[str] = None,
    session_only: bool = False,
    without_context: bool = False,
) -> Optional[User]:
    """
    Get authenticated user without database session dependency.

    No longer sets tenant context - pass organization_id and user_id directly to CRUD operations.
    """
    # Try session auth first
    user = await get_current_user(request)
    if user:
        if not user.organization_id and not without_context:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not associated with an organization",
            )
        return user

    # If session_only or no credentials, return None
    if session_only or not credentials:
        return None

    # Try bearer token
    if credentials.credentials.startswith("rh-"):
        token_value = credentials.credentials

        # Use basic session for token validation and user lookup - no organization context needed
        from rhesis.backend.app.auth.token_validation import validate_token
        from rhesis.backend.app.database import get_db

        with get_db() as db:
            is_valid, _ = validate_token(token_value, db=db)

            if is_valid:
                token = get_token_by_value(db, token_value)
                user = get_user_by_id(db, token.user_id)

        # Handle user based on organization requirement
        if user:
            if without_context:
                # without_context allows users without organization
                return user
            else:
                # Require organization_id when not without_context
                if not user.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User is not associated with an organization",
                    )
                # Return user - tenant context should be passed directly to CRUD operations when needed
                return user

    # Try JWT token if secret_key is provided
    if secret_key and not credentials.credentials.startswith("rh-"):
        jwt_user = await get_user_from_jwt(credentials.credentials, secret_key)
        if jwt_user:
            if not jwt_user.organization_id and not without_context:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is not associated with an organization",
                )
            return jwt_user

    return None


async def require_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    """Require authenticated user via session only without database session dependency"""
    user = await get_authenticated_user_with_context(request, credentials, session_only=True)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_MESSAGE)
    return user


async def require_current_user_or_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    secret_key: str = Depends(get_secret_key),
) -> User:
    """Require authenticated user via session or token without database session dependency"""
    user = await get_authenticated_user_with_context(request, credentials, secret_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def get_authenticated_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    secret_key: str = Depends(get_secret_key),
) -> Tuple[Optional[User], Optional[str]]:
    """Get authenticated user and authentication method without database session dependency"""
    user = await get_authenticated_user_with_context(request, credentials, secret_key)
    if not user:
        return None, None

    # Determine authentication method
    if "user_id" in request.session:
        return user, AuthenticationMethod.SESSION
    elif credentials:
        if credentials.credentials.startswith("rh-"):
            return user, AuthenticationMethod.BEARER
        else:
            return user, AuthenticationMethod.JWT

    return None, None


def generate_api_token() -> str:
    """Generate a secure API token in OpenAI-style format"""
    while True:
        token_bytes = secrets.token_bytes(32)
        token_b64 = base64.urlsafe_b64encode(token_bytes).decode("utf-8").rstrip("=")
        if "-" not in token_b64:
            return f"rh-{token_b64}"


async def require_current_user_or_token_without_context(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    secret_key: str = Depends(get_secret_key),
) -> User:
    """Require authenticated user via session or token, without requiring organization context"""
    user = await get_authenticated_user_with_context(
        request, db, credentials, secret_key, without_context=True
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
