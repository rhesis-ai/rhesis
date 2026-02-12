from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Tuple

from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.auth.constants import UNAUTHORIZED_MESSAGE, AuthenticationMethod
from rhesis.backend.app.auth.token_utils import get_secret_key, verify_jwt_token
from rhesis.backend.app.auth.token_validation import validate_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas import UserCreate

if TYPE_CHECKING:
    from rhesis.backend.app.auth.providers.base import AuthUser

bearer_scheme = HTTPBearer(auto_error=False)


def find_or_create_user(db: Session, auth0_id: str, email: str, user_profile: dict) -> User:
    """
    Find existing user or create a new one (legacy Auth0 version).

    This function is kept for backward compatibility during migration.
    New code should use find_or_create_user_from_auth() instead.
    """
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
            user.is_email_verified = True  # Auth via provider confirms email
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
                user.is_email_verified = True  # Auth via provider confirms email
                # Transaction commit is handled by the session context manager
                return user

    # If no user found or emails don't match, create new user
    if not user:
        # Normalize email and verify domain can receive mail
        from rhesis.backend.app.utils.validation import validate_and_normalize_email

        normalized_email = validate_and_normalize_email(email, check_deliverability=True)

        user_data = UserCreate(
            email=normalized_email,
            name=user_profile["name"],
            given_name=user_profile["given_name"],
            family_name=user_profile["family_name"],
            auth0_id=auth0_id,
            picture=user_profile["picture"],
            is_active=True,
            is_superuser=False,
            is_email_verified=True,  # Auth0/IdP has verified the email
            last_login_at=current_time,
        )
        user = crud.create_user(db, user_data)
        is_new_user = True

    # Send welcome email to new users
    if is_new_user:
        _send_welcome_email(user)

    return user


def find_or_create_user_from_auth(db: Session, auth_user: "AuthUser") -> User:
    """
    Find existing user or create a new one from provider-agnostic AuthUser.

    This is the new provider-agnostic version that replaces find_or_create_user.
    Users are matched primarily by email, with provider info updated on each login.

    Args:
        db: Database session
        auth_user: AuthUser dataclass from any authentication provider

    Returns:
        User instance (existing or newly created)
    """
    from rhesis.backend.app.auth.providers.base import AuthUser as AuthUserClass
    from rhesis.backend.app.utils.validation import validate_and_normalize_email
    from rhesis.backend.logging.rhesis_logger import logger

    if not isinstance(auth_user, AuthUserClass):
        raise TypeError(f"Expected AuthUser, got {type(auth_user)}")

    current_time = datetime.now(timezone.utc)
    is_new_user = False

    # Normalize email for lookup (no DNS check on login)
    normalized_email = validate_and_normalize_email(auth_user.email)

    # First try to find user by email (this is our primary matching criteria)
    user = crud.get_user_by_email(db, normalized_email)

    if user:
        # Found user by email - update profile info and provider details
        logger.info(f"Found existing user by email: {normalized_email}")
        user.name = auth_user.name or user.name
        user.given_name = auth_user.given_name or user.given_name
        user.family_name = auth_user.family_name or user.family_name
        user.picture = auth_user.picture or user.picture
        user.provider_type = auth_user.provider_type
        user.external_provider_id = auth_user.external_id
        user.last_login_at = current_time
        # Authenticating via any provider confirms email ownership
        user.is_email_verified = True
        return user

    # Verify domain can receive mail before creating a new account
    normalized_email = validate_and_normalize_email(auth_user.email, check_deliverability=True)

    # Create new user
    logger.info(f"Creating new user: {normalized_email} via {auth_user.provider_type}")
    user_data = UserCreate(
        email=normalized_email,
        name=auth_user.name,
        given_name=auth_user.given_name,
        family_name=auth_user.family_name,
        picture=auth_user.picture,
        provider_type=auth_user.provider_type,
        external_provider_id=auth_user.external_id,
        is_active=True,
        is_superuser=False,
        is_email_verified=True,  # OAuth/credentials auth confirms email ownership
        last_login_at=current_time,
    )
    user = crud.create_user(db, user_data)
    is_new_user = True

    # Send welcome email to new users
    if is_new_user:
        _send_welcome_email(user)

    return user


def _send_welcome_email(user: User) -> None:
    """
    Send welcome email to a new user.

    Args:
        user: The newly created user
    """
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
            logger.info(f"Email service not configured, skipping welcome email for {user.email}")

    except Exception as e:
        # Log the error but don't fail user creation
        from rhesis.backend.logging.rhesis_logger import logger

        logger.error(f"Error sending welcome email to {user.email}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")


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
        # Set user on request state for middleware access (e.g., telemetry)
        request.state.user = user
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
                            request.state.user = user
                            return user
                        else:
                            # Require organization_id when not without_context
                            if not organization_id:
                                raise HTTPException(
                                    status_code=status.HTTP_403_FORBIDDEN,
                                    detail="User is not associated with an organization",
                                )
                            # Return user - tenant context should be passed
                            # directly to CRUD operations when needed
                            request.state.user = user
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
            request.state.user = jwt_user
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


async def authenticate_websocket(websocket: WebSocket) -> User:
    """
    Authenticate WebSocket connection using Bearer token.

    Thin wrapper around get_authenticated_user_with_context that extracts
    credentials from WebSocket headers. Requires organization context.
    Does not accept the connection - that's the endpoint's responsibility.

    Args:
        websocket: The WebSocket connection to authenticate

    Returns:
        User: Authenticated user with organization_id

    Raises:
        HTTPException: If authentication fails or user lacks organization
    """
    # Extract and validate Authorization header
    auth_header = websocket.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    # Create credentials object
    token_value = auth_header.replace("Bearer ", "")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_value)

    # Create minimal mock request (websockets don't have full Request object)
    class MockRequest:
        def __init__(self):
            self.session = {}
            self.state = type("obj", (object,), {})()

    mock_request = MockRequest()

    # Use existing authentication logic (supports both rh- tokens and JWT)
    user = await get_authenticated_user_with_context(
        request=mock_request,
        credentials=credentials,
        secret_key=get_secret_key(),
        without_context=False,  # Require organization
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )

    return user
