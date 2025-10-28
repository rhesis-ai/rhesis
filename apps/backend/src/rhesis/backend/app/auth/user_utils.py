from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.auth.constants import UNAUTHORIZED_MESSAGE, AuthenticationMethod
from rhesis.backend.app.auth.token_utils import get_secret_key, verify_jwt_token
from rhesis.backend.app.auth.token_validation import validate_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas import UserCreate

bearer_scheme = HTTPBearer(auto_error=False)


def find_or_create_user(db: Session, auth0_id: str, email: str, user_profile: dict) -> User:
    """Find existing user or create a new one"""
    user = None
    current_time = datetime.now(timezone.utc)
    is_new_user = False

    # First try to find user by email (this is our primary matching criteria)
    if email:
        user = crud.get_user_by_email(db, email)
        if user:
            # Found user by email - update profile info, auth0_id, and last login
            user.name = user_profile["name"]
            user.given_name = user_profile["given_name"]
            user.family_name = user_profile["family_name"]
            user.picture = user_profile["picture"]
            user.auth0_id = auth0_id
            user.last_login_at = current_time
            # Transaction commit is handled by the session context manager
            return user

    # If not found by email, try auth0_id as fallback
    if not user and auth0_id:
        user = crud.get_user_by_auth0_id(db, auth0_id)
        if user:
            # If emails don't match, we should create a new user
            if email.lower() != user.email.lower():
                user = None
            else:
                # Only update profile info and last login if emails match
                user.name = user_profile["name"]
                user.given_name = user_profile["given_name"]
                user.family_name = user_profile["family_name"]
                user.picture = user_profile["picture"]
                user.last_login_at = current_time
                # Transaction commit is handled by the session context manager
                return user

    # If no user found or emails don't match, create new user
    if not user:
        # Normalize email before creating user
        from rhesis.backend.app.utils.validation import validate_and_normalize_email

        try:
            normalized_email = validate_and_normalize_email(email)
        except ValueError:
            # If email validation fails, use the original email (for placeholder emails)
            normalized_email = email

        user_data = UserCreate(
            email=normalized_email,
            name=user_profile["name"],
            given_name=user_profile["given_name"],
            family_name=user_profile["family_name"],
            auth0_id=auth0_id,
            picture=user_profile["picture"],
            is_active=True,
            is_superuser=False,
            last_login_at=current_time,
        )
        user = crud.create_user(db, user_data)
        is_new_user = True

    # Send welcome email to new users
    if is_new_user:
        try:
            from rhesis.backend.logging.rhesis_logger import logger
            from rhesis.backend.notifications.email.service import EmailService

            email_service = EmailService()

            if email_service.is_configured:
                logger.info(f"Sending welcome email to new user: {user.email}")

                success = email_service.send_welcome_email(
                    recipient_email=user.email,
                    recipient_name=user.name or user.given_name,
                )

                if success:
                    logger.info(f"Successfully sent welcome email to {user.email}")
                else:
                    logger.warning(f"Failed to send welcome email to {user.email}")
            else:
                logger.info(
                    f"Email service not configured, skipping welcome email for {user.email}"
                )

        except Exception as e:
            # Log the error but don't fail user creation
            from rhesis.backend.logging.rhesis_logger import logger

            logger.error(f"Error sending welcome email to {user.email}: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")

    return user


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

    with get_db() as db:
        user = crud.get_user_by_id(db, user_id)

    # User must have an organization_id to proceed
    if not user or not user.organization_id:
        return None

    return user


async def get_user_from_jwt(token: str, secret_key: str) -> Optional[User]:
    """
    Get user from JWT token using simple database session.

    Uses a simple session to get user. The caller is responsible for checking
    whether the user needs an organization_id (via without_context parameter).
    """
    try:
        payload = verify_jwt_token(token, secret_key)
        user_info = payload.get("user", {})
        user_id = user_info.get("id")

        if user_id:
            # Get the user with a basic session - no organization context needed for user lookup
            from rhesis.backend.app.database import get_db

            with get_db() as db:
                user = crud.get_user_by_id(db, user_id)

            if not user:
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
        from rhesis.backend.app.database import get_db

        with get_db() as db:
            is_valid, _ = validate_token(token_value, db=db)

            if is_valid:
                token = crud.get_token_by_value(db, token_value)
                if token:
                    user = crud.get_user_by_id(db, token.user_id)

                    # Handle user based on organization requirement
                    # Must be inside the context manager
                    if user:
                        # Access all attributes we need within transaction context
                        organization_id = user.organization_id

                        if without_context:
                            # without_context allows users without organization
                            return user
                        else:
                            # Require organization_id when not without_context
                            if not organization_id:
                                raise HTTPException(
                                    status_code=status.HTTP_403_FORBIDDEN,
                                    detail="User is not associated with an organization",
                                )
                            # Return user - tenant context passed to CRUD ops
                            return user

    # Try JWT token if secret_key is provided
    if secret_key and credentials and not credentials.credentials.startswith("rh-"):
        jwt_user = await get_user_from_jwt(credentials.credentials, secret_key)
        if jwt_user:
            if not jwt_user.organization_id and not without_context:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is not associated with an organization",
                )
            return jwt_user

    return None


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


async def require_current_user_or_token_without_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    secret_key: str = Depends(get_secret_key),
) -> User:
    """Require authenticated user via session or token, without organization context."""
    user = await get_authenticated_user_with_context(
        request, credentials, secret_key, without_context=True
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
