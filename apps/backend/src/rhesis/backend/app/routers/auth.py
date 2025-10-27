import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from rhesis.backend.app.auth.oauth import extract_user_data, get_auth0_user_info, oauth
from rhesis.backend.app.auth.token_utils import (
    create_session_token,
    get_secret_key,
    verify_jwt_token,
)
from rhesis.backend.app.auth.url_utils import build_redirect_url
from rhesis.backend.app.auth.user_utils import find_or_create_user
from rhesis.backend.app.dependencies import (
    get_db_session,
)
from rhesis.backend.logging import logger

router = APIRouter(prefix="/auth", tags=["authentication"])


def get_callback_url(request: Request) -> str:
    """
    Generate the OAuth callback URL.
    In local development, use request.base_url to match the incoming host.
    In production, use RHESIS_BASE_URL for proper domain handling.
    """
    rhesis_base_url = os.getenv("RHESIS_BASE_URL")
    if rhesis_base_url and (
        "localhost" not in str(request.base_url) and "127.0.0.1" not in str(request.base_url)
    ):
        # Production: use RHESIS_BASE_URL
        base_url = rhesis_base_url.rstrip("/")
    else:
        # Local development: use the actual request host to ensure cookie domain matches
        base_url = str(request.base_url).rstrip("/")

    callback_url = f"{base_url}/auth/callback"

    # Only rewrite http to https if not localhost (including 127.0.0.1)
    if (
        callback_url.startswith("http://")
        and "localhost" not in callback_url
        and "127.0.0.1" not in callback_url
    ):
        callback_url = "https://" + callback_url[7:]

    return callback_url


def get_callback_url(request: Request) -> str:
    """
    Generate the OAuth callback URL.
    In local development, use request.base_url to match the incoming host.
    In production, use RHESIS_BASE_URL for proper domain handling.
    """
    rhesis_base_url = os.getenv("RHESIS_BASE_URL")
    if rhesis_base_url and ("localhost" not in str(request.base_url) and "127.0.0.1" not in str(request.base_url)):
        # Production: use RHESIS_BASE_URL
        base_url = rhesis_base_url.rstrip("/")
    else:
        # Local development: use the actual request host to ensure cookie domain matches
        base_url = str(request.base_url).rstrip("/")
    
    callback_url = f"{base_url}/auth/callback"
    
    # Only rewrite http to https if not localhost (including 127.0.0.1)
    if (
        callback_url.startswith("http://")
        and "localhost" not in callback_url
        and "127.0.0.1" not in callback_url
    ):
        callback_url = "https://" + callback_url[7:]
    
    return callback_url


@router.get("/login")
async def login(request: Request, connection: str = None, return_to: str = "/home"):
    """Redirect users to Auth0 login page"""
    # Store the origin in session for callback
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        request.session["original_frontend"] = origin

    callback_url = get_callback_url(request)

    # Store return_to in session
    request.session["return_to"] = return_to

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
        return await oauth.auth0.authorize_redirect(request, **auth_params)

    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db_session)):
    """Handle the Auth0 callback after successful authentication"""
    try:
        # Step 1: Get token and user info from Auth0
        token, userinfo = await get_auth0_user_info(request)

        # Step 2: Extract and normalize user data
        auth0_id, email, user_profile = extract_user_data(userinfo)

        # Step 3: Find or create user
        user = find_or_create_user(db, auth0_id, email, user_profile)

        # Step 4: Set up session and create token
        request.session["user_id"] = str(user.id)
        session_token = create_session_token(user)

        # Step 5: Determine redirect URL
        redirect_url = build_redirect_url(request, session_token)

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"Auth callback error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/logout")
async def logout(request: Request, post_logout: bool = False, session_token: str = None):
    """Log out the user and clear their session"""
    from fastapi.responses import JSONResponse

    # Clear session data
    request.session.clear()

    # If session token is provided, validate it and clear any related server-side data
    if session_token:
        try:
            secret_key = get_secret_key()
            payload = verify_jwt_token(session_token, secret_key)
            user_info = payload.get("user", {})
            user_id = user_info.get("id")

            if user_id:
                logger.info(f"Logout called for user {user_id} via JWT token")
                # Here you could add additional cleanup if needed
                # For example, invalidating refresh tokens, clearing user-specific cache, etc.

        except JWTError as e:
            logger.warning(f"Invalid session token provided during logout: {str(e)}")
            # Continue with logout even if token is invalid
        except Exception as e:
            logger.error(f"Error processing session token during logout: {str(e)}")
            # Continue with logout even if there's an error

    # Create response with cookie clearing headers
    accept_header = request.headers.get("accept", "")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    frontend_env = os.getenv("FRONTEND_ENV", "development")

    # Check if this is an API call (from frontend middleware)
    if "application/json" in accept_header or "api" in request.url.path:
        response = JSONResponse(content={"success": True, "message": "Logged out successfully"})
    else:
        # Redirect to frontend home page
        return_to_url = frontend_url + "/"
        response = RedirectResponse(url=return_to_url)

    # Clear all authentication-related cookies on the server side
    # This ensures logout works even if client-side cookie clearing fails
    cookies_to_clear = [
        "next-auth.session-token",
        "next-auth.csrf-token",
        "next-auth.callback-url",
        "authjs.session-token",
        "authjs.csrf-token",
        "__Host-next-auth.csrf-token",
        "__Secure-next-auth.callback-url",
        "__Secure-next-auth.session-token",
        "session",
    ]

    for cookie_name in cookies_to_clear:
        # Clear cookie with default settings
        response.set_cookie(
            key=cookie_name, value="", max_age=0, expires=0, path="/", httponly=True, samesite="lax"
        )

        # For staging and production, also clear with domain settings
        if frontend_env in ["staging", "production"]:
            domain = "rhesis.ai" if frontend_env == "production" else "stg.rhesis.ai"

            response.set_cookie(
                key=cookie_name,
                value="",
                max_age=0,
                expires=0,
                path="/",
                domain=domain,
                httponly=True,
                secure=True,
                samesite="lax",
            )
            # Also clear with leading dot for broader coverage
            response.set_cookie(
                key=cookie_name,
                value="",
                max_age=0,
                expires=0,
                path="/",
                domain=f".{domain}",
                httponly=True,
                secure=True,
                samesite="lax",
            )

    logger.info("Logout completed, cookies cleared")
    return response


@router.get("/verify")
async def verify_auth(
    request: Request,
    session_token: str,
    return_to: str = "/home",
    secret_key: str = Depends(get_secret_key),
):
    """Verify JWT session token and return user info"""
    logger.info(f"Verify request received. Token: {session_token[:8]}...")

    try:
        # Use the shared verification function
        payload = verify_jwt_token(session_token, secret_key)

        # Return the user info from the token
        return {"authenticated": True, "user": payload["user"], "return_to": return_to}

    except JWTError as e:
        logger.error(f"JWT verification failed: {str(e)}")
        if "Expired token" in str(e):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except Exception as e:
        logger.error(f"Error verifying token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )


@router.get("/demo")
async def demo_redirect(request: Request):
    """Redirect to Auth0 login with demo user pre-filled"""
    try:
        logger.info("Demo redirect requested")

        # Demo user email
        DEMO_EMAIL = os.getenv("DEMO_USER_EMAIL", "demo@rhesis.ai")

        # Store the origin in session for callback
        origin = request.headers.get("origin") or request.headers.get("referer")
        if origin:
            request.session["original_frontend"] = origin

        callback_url = get_callback_url(request)

        # Store return_to in session - demo users go to dashboard
        request.session["return_to"] = "/dashboard"

        if not os.getenv("AUTH0_DOMAIN"):
            raise HTTPException(status_code=500, detail="AUTH0_DOMAIN not configured")

        # Auth0 authorization parameters with login_hint for demo user
        auth_params = {
            "redirect_uri": callback_url,
            "audience": f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/",
            "login_hint": DEMO_EMAIL,  # Pre-fills the email field
            "prompt": "login",  # Always show login screen
        }

        # Use the existing OAuth redirect but with demo-specific parameters
        response = await oauth.auth0.authorize_redirect(request, **auth_params)

        logger.info(f"Demo redirect created with login_hint: {DEMO_EMAIL}")
        return response

    except Exception as e:
        logger.error(f"Demo redirect error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Demo redirect failed: {str(e)}")
