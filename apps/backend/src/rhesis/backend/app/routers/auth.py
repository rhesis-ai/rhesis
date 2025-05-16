import os
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.auth.auth_utils import ALGORITHM, get_secret_key
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.logging import logger

# OAuth configuration
oauth = OAuth()
oauth.register(
    "auth0",
    client_id=os.getenv("AUTH0_CLIENT_ID"),
    client_secret=os.getenv("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f"https://{os.getenv('AUTH0_DOMAIN')}/.well-known/openid-configuration",
)

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)

# Constants
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours
FRONTEND_DOMAINS = [
    "app.rhesis.ai",
    "localhost:3000",  # development
]


def create_session_token(user: User) -> str:
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


# Routes remain the same but use imported authentication utilities
@router.get("/login")
async def login(request: Request, connection: str = None, return_to: str = "/home"):
    """Redirect users to Auth0 login page"""
    # Store the origin in session for callback
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        request.session["original_frontend"] = origin

    base_url = str(request.base_url).rstrip("/")
    callback_url = f"{base_url}/auth/callback"

    # Store return_to in session
    request.session["return_to"] = return_to

    # Only rewrite http to https if not localhost
    if callback_url.startswith("http://") and "localhost" not in callback_url:
        callback_url = "https://" + callback_url[7:]

    if not os.getenv("AUTH0_DOMAIN"):
        raise HTTPException(status_code=500, detail="AUTH0_DOMAIN not configured")

    try:
        # Add connection parameter if provided
        auth_params = {
            "redirect_uri": callback_url,
            "audience": f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/",
            "prompt": "login",
        }
        if connection:
            auth_params["connection"] = connection

        # Let oauth.authorize_redirect handle state parameter
        response = await oauth.auth0.authorize_redirect(request, **auth_params)

        # Log the state for debugging
        logger.info(f"Generated state: {request.session.get('oauth_state')}")

        return response

    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    """Handle the Auth0 callback after successful authentication"""
    try:
        # Step 1: Get token and user info from Auth0
        token, userinfo = await _get_auth0_user_info(request)

        # Step 2: Extract and normalize user data
        auth0_id, email, user_profile = _extract_user_data(userinfo)

        # Step 3: Find or create user
        user = _find_or_create_user(db, auth0_id, email, user_profile)

        # Step 4: Set up session and create token
        request.session["user_id"] = str(user.id)
        session_token = create_session_token(user)

        # Step 5: Determine redirect URL
        redirect_url = _build_redirect_url(request, session_token)

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"Auth callback error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


async def _get_auth0_user_info(request: Request):
    """Get user information from Auth0"""

    token = await oauth.auth0.authorize_access_token(request)
    userinfo = await oauth.auth0.userinfo(token=token)
    return token, userinfo


def _extract_user_data(userinfo):
    """Extract and normalize user data from Auth0 userinfo"""
    # Extract basic user information
    auth0_id = userinfo.get("sub")
    email = userinfo.get("email")

    # Create user profile dictionary
    user_profile = {
        "name": userinfo.get("name"),
        "given_name": userinfo.get("given_name"),
        "family_name": userinfo.get("family_name"),
        "picture": userinfo.get("picture"),
    }

    # Handle missing email for GitHub users
    if not email and auth0_id:
        email = _generate_placeholder_email(auth0_id)

    return auth0_id, email, user_profile


def _generate_placeholder_email(auth0_id):
    """Generate a placeholder email for users without an email"""
    provider_parts = auth0_id.split("|")

    if len(provider_parts) == 2 and provider_parts[0] == "github":
        github_id = provider_parts[1]
        email = f"github-user-{github_id}@placeholder.rhesis.ai"
        logger.info(f"Created placeholder email for GitHub user: {email}")
    else:
        # For other providers with missing email
        email = f"user-{auth0_id.replace('|', '-')}@placeholder.rhesis.ai"
        logger.info(f"Created placeholder email for user: {email}")

    # Ensure we have an email (last resort fallback)
    if not email:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        email = f"unknown-user-{timestamp}@placeholder.rhesis.ai"
        logger.warning(f"No email provided, using generated placeholder: {email}")

    return email


def _find_or_create_user(db, auth0_id, email, user_profile):
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
        user_data = schemas.UserCreate(
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


def _build_redirect_url(request, session_token):
    """Build the redirect URL with session token"""
    # Get the original frontend URL from session or fallback to environment variable
    original_frontend = request.session.get("original_frontend")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    if original_frontend:
        parsed_origin = urlparse(original_frontend)
        # Check if origin is localhost (any port) or matches allowed domains
        if "localhost" in parsed_origin.netloc:
            frontend_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}"
        elif any(domain in parsed_origin.netloc for domain in FRONTEND_DOMAINS):
            frontend_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}"

        # Clean up session
        request.session.pop("original_frontend", None)

    # Get return_to path from session or default to dashboard
    return_to = request.session.get("return_to", "/dashboard")
    request.session.pop("return_to", None)

    # Parse return_to if it's a full URL and extract just the path
    if return_to.startswith("http"):
        parsed = urlparse(return_to)
        # Extract path and query parameters if any
        return_to = parsed.path
        if parsed.query:
            query_params = parse_qs(parsed.query)
            if "return_to" in query_params:
                # Get the actual destination from nested return_to
                return_to = query_params["return_to"][0]

    # Ensure return_to starts with a slash
    return_to = f"/{return_to.lstrip('/')}"

    # Redirect to signin page with session token and clean return_to
    final_url = f"{frontend_url.rstrip('/')}/auth/signin"
    final_url = f"{final_url}?session_token={session_token}&return_to={return_to}"

    return final_url


@router.get("/logout")
async def logout(request: Request, post_logout: bool = False):
    """Log out the user and clear their session"""
    # Clear session data
    request.session.clear()

    # Construct Auth0 logout URL
    auth0_domain = os.getenv("AUTH0_DOMAIN")
    client_id = os.getenv("AUTH0_CLIENT_ID")
    # Use FRONTEND_URL environment variable for returnTo
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # If post_logout is True, return to root, otherwise use the frontend URL
    return_to_url = frontend_url + ("/" if post_logout else "")

    # Redirect to Auth0 logout endpoint
    logout_url = f"https://{auth0_domain}/v2/logout?client_id={client_id}&returnTo={return_to_url}"

    return RedirectResponse(url=logout_url)


@router.get("/verify")
async def verify_auth(
    request: Request,
    session_token: str,
    return_to: str = "/home",
    db: Session = Depends(get_db),
    secret_key: str = Depends(get_secret_key),
):
    """Verify JWT session token and return user info"""
    logger.info(f"Verify request received. Token: {session_token[:8]}...")

    try:
        # Verify the JWT token
        payload = jwt.decode(session_token, secret_key, algorithms=[ALGORITHM])

        # Check if it's a session token
        if payload.get("type") != "session":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

        # Return the user info from the token
        return {"authenticated": True, "user": payload["user"], "return_to": return_to}

    except JWTError as e:
        logger.error(f"JWT verification failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )
