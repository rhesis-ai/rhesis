import base64
import os
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from rhesis.backend.app.crud import get_token_by_value, get_user_by_id
from rhesis.backend.app.database import get_db, set_tenant
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


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get current user from session"""
    if "user_id" not in request.session:
        return None

    user_id = request.session.get("user_id")
    user = get_user_by_id(db, user_id)

    # Set the tenant context (organization_id) for the session, if available
    if user:
        if user.organization_id:
            set_tenant(db, str(user.organization_id), str(user.id))
        else:
            set_tenant(db, user_id=str(user.id))

    return user


async def get_user_from_jwt(
    token: str, db: Session, secret_key: str, algorithm: str = ALGORITHM
) -> Optional[User]:
    """Get user from JWT token"""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        if payload.get("type") != "session":
            return None
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
        db.commit()
    except Exception as e:
        logger.error(f"Failed to update token last_used_at: {str(e)}")
        db.rollback()


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

    # Make sure token.expires_at is timezone-aware
    token_expiry = (
        token.expires_at
        if token.expires_at.tzinfo
        else token.expires_at.replace(tzinfo=timezone.utc)
    )
    now = datetime.now(timezone.utc)

    if token.expires_at and token_expiry <= now:
        return False, "Token has expired"

    if update_usage and db:
        update_token_usage(db, token)

    return True, None


async def get_authenticated_user_with_context(
    request: Request,
    db: Session,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    secret_key: Optional[str] = None,
    session_only: bool = False,
    without_context: bool = False,
) -> Optional[User]:
    """Get authenticated user and set tenant context"""
    # Try session auth first
    user = await get_current_user(request, db)
    if user:
        if not user.organization_id and not without_context:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not associated with an organization",
            )
        if user.organization_id:
            set_tenant(db, str(user.organization_id), str(user.id))
        else:
            set_tenant(db, user_id=str(user.id))
        return user

    # If session_only or no credentials, return None
    if session_only or not credentials:
        return None

    # Try bearer token
    if credentials.credentials.startswith("rh-"):
        token_value = credentials.credentials
        is_valid, _ = validate_token(token_value, db=db)

        if is_valid:
            token = get_token_by_value(db, token_value)
            user = get_user_by_id(db, token.user_id)
            if user:
                if not user.organization_id and not without_context:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User is not associated with an organization",
                    )
                if user.organization_id:
                    set_tenant(db, str(user.organization_id), str(user.id))
                else:
                    set_tenant(db, user_id=str(user.id))
                return user

    # Try JWT token if secret_key is provided
    if secret_key and not credentials.credentials.startswith("rh-"):
        jwt_user = await get_user_from_jwt(credentials.credentials, db, secret_key)
        if jwt_user:
            if not jwt_user.organization_id and not without_context:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is not associated with an organization",
                )
            if jwt_user.organization_id:
                set_tenant(db, str(jwt_user.organization_id), str(jwt_user.id))
            else:
                set_tenant(db, user_id=str(jwt_user.id))
            return jwt_user

    return None


async def require_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    """Require authenticated user via session only"""
    user = await get_authenticated_user_with_context(request, db, credentials, session_only=True)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_MESSAGE)
    return user


async def require_current_user_or_token(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    secret_key: str = Depends(get_secret_key),
) -> User:
    """Require authenticated user via session or token"""
    user = await get_authenticated_user_with_context(request, db, credentials, secret_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def get_authenticated_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    secret_key: str = Depends(get_secret_key),
) -> Tuple[Optional[User], Optional[str]]:
    """Get authenticated user and authentication method"""
    user = await get_authenticated_user_with_context(request, db, credentials, secret_key)
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
