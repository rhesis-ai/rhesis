import base64
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt

from rhesis.backend.app.auth.constants import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.redact import redact_email
from rhesis.backend.logging import logger

# Token expiry defaults (in minutes)
EMAIL_VERIFICATION_EXPIRE_MINUTES = 60 * 24  # 24 hours
PASSWORD_RESET_EXPIRE_MINUTES = 60  # 1 hour
MAGIC_LINK_EXPIRE_MINUTES = 15  # 15 minutes
AUTH_CODE_EXPIRE_MINUTES = 1  # 60 seconds, for OAuth callback redirect


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
        "sub": str(user.id),
        "iat": now,
        "exp": expire,
        "type": "session",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "is_superuser": user.is_superuser,
            "is_email_verified": getattr(user, "is_email_verified", True),
            "organization_id": organization_id,
        },
    }

    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def verify_jwt_token(token: str, secret_key: str, algorithm: str = ALGORITHM) -> Dict[str, Any]:
    """
    Verify and decode a JWT token with explicit expiration checks.
    Returns the decoded payload if valid, raises JWTError if not.
    """
    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require_exp": True,
                "require_iat": True,
            },
        )

        # Check if it's a session token
        if payload.get("type") != "session":
            logger.warning(f"Invalid token type: {payload.get('type')}")
            raise JWTError("Invalid token type")

        if "user" in payload:
            logger.debug(
                "JWT token validated for user: %s",
                redact_email(payload["user"].get("email") or ""),
            )
            logger.debug(
                f"Token expiration: {datetime.fromtimestamp(payload['exp'], tz=timezone.utc)}"
            )

        return payload

    except JWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        if "Expired token" in str(e):
            logger.warning("JWT token has expired")
        raise


# =========================================================================
# Email flow tokens (verification, password reset, magic link)
# =========================================================================


def _create_email_flow_token(
    user_id: str,
    email: str,
    token_type: str,
    expire_minutes: int,
    extra_claims: Optional[Dict[str, Any]] = None,
    *,
    with_jti: bool = False,
) -> str:
    """
    Create a short-lived JWT for email-based flows.

    Args:
        user_id: The user's ID (as string).
        email: The user's email address.
        token_type: One of 'email_verification', 'password_reset',
                    or 'magic_link'.
        expire_minutes: Token lifetime in minutes.
        extra_claims: Optional additional claims.
        with_jti: If True, add a unique jti claim for single-use tracking.

    Returns:
        Signed JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    if with_jti:
        payload["jti"] = str(uuid.uuid4())
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def create_email_verification_token(user_id: str, email: str) -> str:
    """Create a 24-hour email verification token."""
    return _create_email_flow_token(
        user_id=user_id,
        email=email,
        token_type="email_verification",
        expire_minutes=EMAIL_VERIFICATION_EXPIRE_MINUTES,
    )


def create_password_reset_token(user_id: str, email: str) -> str:
    """Create a 1-hour single-use password reset token."""
    return _create_email_flow_token(
        user_id=user_id,
        email=email,
        token_type="password_reset",
        expire_minutes=PASSWORD_RESET_EXPIRE_MINUTES,
        with_jti=True,
    )


def create_magic_link_token(user_id: str, email: str) -> str:
    """Create a 15-minute single-use magic link login token."""
    return _create_email_flow_token(
        user_id=user_id,
        email=email,
        token_type="magic_link",
        expire_minutes=MAGIC_LINK_EXPIRE_MINUTES,
        with_jti=True,
    )


def verify_email_flow_token(token: str, expected_type: str) -> Dict[str, Any]:
    """
    Verify a token from an email flow (verification, reset, magic link).

    Args:
        token: The JWT token string.
        expected_type: The expected ``type`` claim.

    Returns:
        Decoded payload dict with ``sub``, ``email``, ``type``.

    Raises:
        HTTPException: If the token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            get_secret_key(),
            algorithms=[ALGORITHM],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require_exp": True,
                "require_iat": True,
            },
        )
    except JWTError as e:
        detail = "Token has expired" if "Expired" in str(e) else ("Invalid token")
        logger.warning(f"Email flow token error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token type",
        )

    return payload


def create_auth_code(session_token: str) -> str:
    """Create a short-lived JWT auth code wrapping a session token.

    Used during OAuth callback redirects so the long-lived session token
    is never exposed in the URL.  The auth code expires in 60 seconds.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "type": "auth_code",
        "session_token": session_token,
        "exp": now + timedelta(minutes=AUTH_CODE_EXPIRE_MINUTES),
        "iat": now,
    }
    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def verify_auth_code(code: str) -> str:
    """Verify a short-lived auth code and return the wrapped session token.

    Raises HTTPException(400) if the code is invalid or expired.
    """
    try:
        payload = jwt.decode(code, get_secret_key(), algorithms=[ALGORITHM])
    except JWTError as e:
        logger.warning(f"Auth code verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired auth code",
        )

    if payload.get("type") != "auth_code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid auth code type",
        )

    session_token = payload.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth code missing session token",
        )

    return session_token


def generate_api_token() -> str:
    """Generate a secure API token in OpenAI-style format"""
    while True:
        token_bytes = secrets.token_bytes(32)
        token_b64 = base64.urlsafe_b64encode(token_bytes).decode("utf-8").rstrip("=")
        if "-" not in token_b64:
            return f"rh-{token_b64}"
