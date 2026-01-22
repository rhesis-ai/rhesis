import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from jose import JWTError
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from rhesis.backend.app.auth.providers import ProviderRegistry
from rhesis.backend.app.auth.session_invalidation import (
    clear_user_logout,
    invalidate_user_sessions,
    is_session_valid,
)
from rhesis.backend.app.auth.token_utils import (
    create_session_token,
    get_secret_key,
    verify_jwt_token,
)
from rhesis.backend.app.auth.url_utils import build_redirect_url
from rhesis.backend.app.auth.user_utils import (
    find_or_create_user,
    find_or_create_user_from_auth,
)
from rhesis.backend.app.dependencies import (
    get_db_session,
)
from rhesis.backend.logging import logger
from rhesis.backend.telemetry import (
    is_telemetry_enabled,
    set_telemetry_enabled,
    track_user_activity,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


# =============================================================================
# Request/Response Models
# =============================================================================


class EmailLoginRequest(BaseModel):
    """Request body for email/password login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class EmailRegisterRequest(BaseModel):
    """Request body for email/password registration."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    name: Optional[str] = None


class ProviderInfo(BaseModel):
    """Information about an authentication provider."""

    name: str
    display_name: str
    type: str  # 'oauth' or 'credentials'
    enabled: bool
    registration_enabled: Optional[bool] = None


class ProvidersResponse(BaseModel):
    """Response for /auth/providers endpoint."""

    providers: List[ProviderInfo]


# =============================================================================
# Helper Functions
# =============================================================================


def get_callback_url(request: Request, provider: Optional[str] = None) -> str:
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


def _is_legacy_auth0_enabled() -> bool:
    """Check if legacy Auth0 authentication is enabled for rollback."""
    enabled = os.getenv("AUTH_LEGACY_AUTH0_ENABLED", "false").lower()
    return enabled in ("true", "1", "yes")


# =============================================================================
# Provider Discovery Endpoint
# =============================================================================


@router.get("/providers", response_model=ProvidersResponse)
async def get_providers():
    """
    Get list of enabled authentication providers.

    Returns information about all configured and enabled authentication
    providers. The frontend uses this to dynamically render login options.
    """
    ProviderRegistry.initialize()
    providers = ProviderRegistry.get_provider_info()
    return ProvidersResponse(providers=[ProviderInfo(**p) for p in providers])


# =============================================================================
# OAuth Login Endpoints
# =============================================================================


@router.get("/login/{provider}")
async def login_with_provider(
    request: Request,
    provider: str,
    return_to: str = "/home",
):
    """
    Initiate OAuth login with a specific provider.

    Args:
        provider: Provider name (e.g., 'google', 'github')
        return_to: URL to redirect to after successful login
    """
    ProviderRegistry.initialize()
    auth_provider = ProviderRegistry.get_provider(provider)

    if not auth_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown authentication provider: {provider}",
        )

    if not auth_provider.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication provider '{provider}' is not configured",
        )

    if not auth_provider.is_oauth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Provider '{provider}' does not support OAuth login. Use POST /auth/login/email"
            ),
        )

    # Store session data for callback
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        request.session["original_frontend"] = origin
    request.session["return_to"] = return_to
    request.session["auth_provider"] = provider

    callback_url = get_callback_url(request, provider)

    try:
        return await auth_provider.get_authorization_url(request, callback_url)
    except Exception as e:
        logger.error(f"OAuth login error for {provider}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to initiate {provider} login: {str(e)}",
        )


@router.get("/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db_session)):
    """
    Handle OAuth callback from any provider.

    This endpoint handles the callback from OAuth providers after the user
    has authenticated. It determines which provider initiated the flow
    from session data and completes the authentication.
    """
    # Determine which provider initiated this callback
    provider_name = request.session.get("auth_provider")

    # If no provider in session, try to detect from state or fall back to legacy
    if not provider_name:
        # Check if legacy Auth0 is enabled for backward compatibility
        if _is_legacy_auth0_enabled():
            return await _legacy_auth0_callback(request, db)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No authentication provider found in session",
        )

    ProviderRegistry.initialize()
    auth_provider = ProviderRegistry.get_provider(provider_name)

    if not auth_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown authentication provider: {provider_name}",
        )

    try:
        # Authenticate with the provider
        auth_user = await auth_provider.authenticate(request)

        # Find or create user
        user = find_or_create_user_from_auth(db, auth_user)

        # Set up session and create token
        request.session["user_id"] = str(user.id)
        clear_user_logout(str(user.id))  # Clear any previous logout invalidation
        session_token = create_session_token(user)

        # Clear provider from session
        request.session.pop("auth_provider", None)

        # Track login activity
        if is_telemetry_enabled():
            set_telemetry_enabled(
                enabled=True,
                user_id=str(user.id),
                org_id=str(user.organization_id) if user.organization_id else None,
            )
            track_user_activity(
                event_type="login",
                session_id=request.session.get("_id"),
                login_method="oauth",
                auth_provider=provider_name,
            )

        # Determine redirect URL
        redirect_url = build_redirect_url(request, session_token)
        return RedirectResponse(url=redirect_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth callback error for {provider_name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}",
        )


# =============================================================================
# Email/Password Authentication Endpoints
# =============================================================================


@router.post("/login/email")
async def login_with_email(
    request: Request,
    body: EmailLoginRequest,
    db: Session = Depends(get_db_session),
):
    """
    Authenticate with email and password.

    Returns a session token on successful authentication.
    """
    ProviderRegistry.initialize()
    email_provider = ProviderRegistry.get_provider("email")

    if not email_provider or not email_provider.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email/password authentication is not enabled",
        )

    try:
        # Authenticate with email provider
        auth_user = await email_provider.authenticate(
            request,
            email=body.email,
            password=body.password,
            db=db,
        )

        # Find or create user (will update last_login_at)
        user = find_or_create_user_from_auth(db, auth_user)

        # Set up session and create token
        request.session["user_id"] = str(user.id)
        clear_user_logout(str(user.id))  # Clear any previous logout invalidation
        session_token = create_session_token(user)

        # Track login activity
        if is_telemetry_enabled():
            set_telemetry_enabled(
                enabled=True,
                user_id=str(user.id),
                org_id=str(user.organization_id) if user.organization_id else None,
            )
            track_user_activity(
                event_type="login",
                session_id=request.session.get("_id"),
                login_method="email",
                auth_provider="email",
            )

        return {
            "success": True,
            "session_token": session_token,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "organization_id": (str(user.organization_id) if user.organization_id else None),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )


@router.post("/register")
async def register_with_email(
    request: Request,
    body: EmailRegisterRequest,
    db: Session = Depends(get_db_session),
):
    """
    Register a new user with email and password.

    Returns a session token on successful registration.
    """
    ProviderRegistry.initialize()
    email_provider = ProviderRegistry.get_provider("email")

    if not email_provider or not email_provider.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email/password authentication is not enabled",
        )

    # Import here to access the register method
    from rhesis.backend.app.auth.providers.email import EmailProvider

    if not isinstance(email_provider, EmailProvider):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email provider configuration error",
        )

    try:
        # Register new user
        await email_provider.register(
            request,
            email=body.email,
            password=body.password,
            name=body.name,
            db=db,
        )

        # The user was already created in register(), so just look them up
        from rhesis.backend.app import crud

        user = crud.get_user_by_email(db, body.email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User creation failed",
            )

        # Set up session and create token
        request.session["user_id"] = str(user.id)
        clear_user_logout(str(user.id))  # Clear any previous logout invalidation
        session_token = create_session_token(user)

        # Track registration activity
        if is_telemetry_enabled():
            set_telemetry_enabled(
                enabled=True,
                user_id=str(user.id),
                org_id=str(user.organization_id) if user.organization_id else None,
            )
            track_user_activity(
                event_type="registration",
                session_id=request.session.get("_id"),
                login_method="email",
                auth_provider="email",
            )

        return {
            "success": True,
            "session_token": session_token,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "organization_id": (str(user.organization_id) if user.organization_id else None),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}",
        )


# =============================================================================
# Legacy Auth0 Support (for migration period)
# =============================================================================


async def _legacy_auth0_callback(request: Request, db: Session):
    """
    Handle legacy Auth0 callback during migration period.

    This function is only called when AUTH_LEGACY_AUTH0_ENABLED=true
    and no native provider was found in session.
    """
    from rhesis.backend.app.auth.oauth import (
        extract_user_data,
        get_auth0_user_info,
    )

    try:
        # Step 1: Get token and user info from Auth0
        token, userinfo = await get_auth0_user_info(request)

        # Step 2: Extract and normalize user data
        auth0_id, email, user_profile = extract_user_data(userinfo)

        # Step 3: Find or create user (legacy method)
        user = find_or_create_user(db, auth0_id, email, user_profile)

        # Step 4: Set up session and create token
        request.session["user_id"] = str(user.id)
        clear_user_logout(str(user.id))  # Clear any previous logout invalidation
        session_token = create_session_token(user)

        # Step 5: Track login activity
        if is_telemetry_enabled():
            set_telemetry_enabled(
                enabled=True,
                user_id=str(user.id),
                org_id=str(user.organization_id) if user.organization_id else None,
            )
            track_user_activity(
                event_type="login",
                session_id=request.session.get("_id"),
                login_method="oauth",
                auth_provider="auth0",
            )

        # Step 6: Determine redirect URL
        redirect_url = build_redirect_url(request, session_token)
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"Legacy Auth0 callback error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}",
        )


@router.get("/login")
async def login(request: Request, connection: str = None, return_to: str = "/home"):
    """
    Legacy Auth0 login endpoint (kept for backward compatibility).

    During migration, this endpoint redirects to Auth0 if AUTH_LEGACY_AUTH0_ENABLED=true.
    Otherwise, it returns an error directing users to use the new provider-specific endpoints.
    """
    if not _is_legacy_auth0_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Legacy Auth0 login is disabled. "
                "Use GET /auth/login/{provider} for OAuth "
                "or POST /auth/login/email for email login."
            ),
        )

    from rhesis.backend.app.auth.oauth import oauth

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

        return await oauth.auth0.authorize_redirect(request, **auth_params)

    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Session Management Endpoints
# =============================================================================


@router.get("/logout")
async def logout(request: Request, post_logout: bool = False, session_token: str = None):
    """Log out the user and clear their session"""
    # Clear session data
    request.session.clear()

    # If session token is provided, validate it and invalidate all user sessions
    if session_token:
        try:
            secret_key = get_secret_key()
            payload = verify_jwt_token(session_token, secret_key)
            user_info = payload.get("user", {})
            user_id = user_info.get("id")

            if user_id:
                logger.info(f"Logout called for user {user_id} via JWT token")

                # Invalidate all sessions for this user
                # This ensures the JWT token can no longer be used
                invalidate_user_sessions(user_id)

                # Track logout activity if telemetry is enabled
                if is_telemetry_enabled():
                    org_id = user_info.get("organization_id")
                    set_telemetry_enabled(
                        enabled=True,
                        user_id=str(user_id),
                        org_id=str(org_id) if org_id else None,
                    )
                    track_user_activity(event_type="logout", session_id=request.session.get("_id"))

        except JWTError as e:
            logger.warning(f"Invalid session token provided during logout: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing session token during logout: {str(e)}")

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
        response.set_cookie(
            key=cookie_name,
            value="",
            max_age=0,
            expires=0,
            path="/",
            httponly=True,
            samesite="lax",
        )

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
        payload = verify_jwt_token(session_token, secret_key)

        # Check if the session was invalidated (user logged out)
        user_id = payload.get("user", {}).get("id")
        iat = payload.get("iat")

        if user_id and iat:
            from datetime import datetime, timezone

            # Convert iat (Unix timestamp) to datetime
            issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)

            if not is_session_valid(user_id, issued_at):
                logger.info(f"Session for user {user_id} was invalidated (logged out)")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has been invalidated",
                )

        return {"authenticated": True, "user": payload["user"], "return_to": return_to}

    except JWTError as e:
        logger.error(f"JWT verification failed: {str(e)}")
        if "Expired token" in str(e):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )


# =============================================================================
# Demo and Quick Start Endpoints
# =============================================================================


@router.get("/demo")
async def demo_redirect(request: Request):
    """Redirect to Auth0 login with demo user pre-filled (legacy)"""
    if not _is_legacy_auth0_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Demo login via Auth0 is disabled. Use Quick Start mode instead.",
        )

    from rhesis.backend.app.auth.oauth import oauth

    try:
        logger.info("Demo redirect requested")
        DEMO_EMAIL = os.getenv("DEMO_USER_EMAIL", "demo@rhesis.ai")

        origin = request.headers.get("origin") or request.headers.get("referer")
        if origin:
            request.session["original_frontend"] = origin

        callback_url = get_callback_url(request)
        request.session["return_to"] = "/dashboard"

        if not os.getenv("AUTH0_DOMAIN"):
            raise HTTPException(status_code=500, detail="AUTH0_DOMAIN not configured")

        auth_params = {
            "redirect_uri": callback_url,
            "audience": f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2/",
            "login_hint": DEMO_EMAIL,
            "prompt": "login",
        }

        response = await oauth.auth0.authorize_redirect(request, **auth_params)
        logger.info(f"Demo redirect created with login_hint: {DEMO_EMAIL}")
        return response

    except Exception as e:
        logger.error(f"Demo redirect error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Demo redirect failed: {str(e)}")


@router.post("/local-login")
async def local_login(request: Request, db: Session = Depends(get_db_session)):
    """
    Quick Start mode authentication endpoint.

    ⚠️ WARNING: This endpoint is for QUICK START ONLY!
    It bypasses normal authentication and logs in as the default admin@local.dev user.
    """
    from rhesis.backend.app import crud
    from rhesis.backend.app.utils.quick_start import is_quick_start_enabled

    hostname = request.url.hostname if request.url.hostname is not None else None
    if not is_quick_start_enabled(hostname=hostname, headers=dict(request.headers)):
        logger.warning("Attempted to use /auth/local-login but Quick Start mode is not enabled")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Quick Start mode is not enabled. "
                "This endpoint is only available in Quick Start / local deployment."
            ),
        )

    logger.warning("⚠️  QUICK START MODE LOGIN - Bypassing authentication!")
    logger.warning("⚠️  This should NEVER be used in production!")

    try:
        user = crud.get_user_by_email(db, "admin@local.dev")

        if not user:
            logger.error("QUICK START MODE user (admin@local.dev) not found in database")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "QUICK START MODE user not found. "
                    "Please ensure the database was initialized with init_local_user.sql"
                ),
            )

        request.session["user_id"] = str(user.id)
        clear_user_logout(str(user.id))  # Clear any previous logout invalidation
        session_token = create_session_token(user)

        logger.info(f"QUICK START MODE login successful for user: {user.email}")

        if is_telemetry_enabled():
            set_telemetry_enabled(
                enabled=True,
                user_id=str(user.id),
                org_id=str(user.organization_id) if user.organization_id else None,
            )
            track_user_activity(
                event_type="login",
                session_id=request.session.get("_id"),
                login_method="local_dev",
                auth_provider="local",
            )

        return {
            "success": True,
            "session_token": session_token,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "organization_id": (str(user.organization_id) if user.organization_id else None),
            },
            "message": "⚠️  QUICK START MODE login - Not for production use!",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QUICK START MODE login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"QUICK START MODE login failed: {str(e)}",
        )
