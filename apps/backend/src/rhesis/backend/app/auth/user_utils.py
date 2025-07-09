from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.database import get_db, set_tenant
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas import UserCreate
from rhesis.backend.logging import logger
from rhesis.backend.app.auth.constants import AuthenticationMethod, UNAUTHORIZED_MESSAGE
from rhesis.backend.app.auth.token_utils import get_secret_key, verify_jwt_token
from rhesis.backend.app.auth.token_validation import validate_token

bearer_scheme = HTTPBearer(auto_error=False)

def find_or_create_user(db: Session, auth0_id: str, email: str, user_profile: dict) -> User:
    """Find existing user or create a new one"""
    user = None

    # First try to find user by email (this is our primary matching criteria)
    if email:
        user = crud.get_user_by_email(db, email)
        if user:
            # Found user by email - only update profile info, not auth0_id
            user.name = user_profile["name"]
            user.given_name = user_profile["given_name"]
            user.family_name = user_profile["family_name"]
            user.picture = user_profile["picture"]
            db.commit()
            return user

    # If not found by email, try auth0_id as fallback
    if not user and auth0_id:
        user = crud.get_user_by_auth0_id(db, auth0_id)
        if user:
            # If emails don't match, we should create a new user
            if email != user.email:
                user = None
            else:
                # Only update profile info if emails match
                user.name = user_profile["name"]
                user.given_name = user_profile["given_name"]
                user.family_name = user_profile["family_name"]
                user.picture = user_profile["picture"]
                db.commit()
                return user

    # If no user found or emails don't match, create new user
    if not user:
        user_data = UserCreate(
            email=email,
            name=user_profile["name"],
            given_name=user_profile["given_name"],
            family_name=user_profile["family_name"],
            auth0_id=auth0_id,
            picture=user_profile["picture"],
            is_active=True,
            is_superuser=False,
        )
        user = crud.create_user(db, user_data)

    return user

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get current user from session"""
    if "user_id" not in request.session:
        return None

    user_id = request.session.get("user_id")
    user = crud.get_user_by_id(db, user_id)

    # Set the tenant context (organization_id) for the session, if available
    if user:
        if user.organization_id:
            set_tenant(db, str(user.organization_id), str(user.id))
        else:
            set_tenant(db, user_id=str(user.id))

    return user

async def get_user_from_jwt(
    token: str, db: Session, secret_key: str
) -> Optional[User]:
    """Get user from JWT token"""
    try:
        payload = verify_jwt_token(token, secret_key)
        user_info = payload.get("user", {})
        user_id = user_info.get("id")
        
        if user_id:
            return crud.get_user_by_id(db, user_id)
            
    except Exception:
        return None
        
    return None

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
            token = crud.get_token_by_value(db, token_value)
            user = crud.get_user_by_id(db, token.user_id)
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