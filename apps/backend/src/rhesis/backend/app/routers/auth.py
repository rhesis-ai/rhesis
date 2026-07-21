import logging
from typing import List, Optional
from urllib.parse import urlparse

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from jwt import PyJWTError as JWTError
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.password_policy import get_password_policy, validate_password
from rhesis.backend.app.auth.provider_hooks import apply_enrichers
from rhesis.backend.app.auth.providers import ProviderRegistry
from rhesis.backend.app.auth.refresh_token_utils import (
    create_refresh_token,
    revoke_all_for_user,
    verify_and_refresh_token,
)
from rhesis.backend.app.auth.session_invalidation import (
    clear_user_logout,
    invalidate_user_sessions,
    is_session_valid,
)
from rhesis.backend.app.auth.session_utils import regenerate_session
from rhesis.backend.app.auth.terms import (
    record_terms_acceptance,
    user_has_accepted_current_terms,
    user_has_prior_terms_acceptance,
)
from rhesis.backend.app.auth.token_utils import (
    MAGIC_LINK_EXPIRE_MINUTES,
    PASSWORD_RESET_EXPIRE_MINUTES,
    create_auth_code,
    create_email_verification_token,
    create_magic_link_token,
    create_password_reset_token,
    create_session_token,
    get_secret_key,
    verify_auth_code,
    verify_email_flow_token,
    verify_jwt_token,
)
from rhesis.backend.app.auth.url_utils import build_redirect_url
from rhesis.backend.app.auth.used_token_store import (
    TokenStoreUnavailableError,
    claim_token_jti,
)
from rhesis.backend.app.auth.user_utils import (
    _send_welcome_email,
    find_or_create_user_from_auth,
    mark_user_joined_if_needed,
    require_current_user_or_token_without_context,
)
from rhesis.backend.app.config.settings import (
    get_application_settings,
    get_frontend_settings,
)
from rhesis.backend.app.dependencies import (
    get_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.quick_start import is_quick_start_enabled
from rhesis.backend.app.utils.rate_limit import (
    AUTH_FORGOT_PASSWORD_LIMIT,
    AUTH_LOGIN_EMAIL_LIMIT,
    AUTH_MAGIC_LINK_LIMIT,
    AUTH_REGISTER_LIMIT,
    AUTH_RESEND_VERIFICATION_LIMIT,
    AUTH_TERMS_STATUS_LIMIT,
    limiter,
)
from rhesis.backend.app.utils.redact import redact_email
from rhesis.backend.telemetry import (
    is_telemetry_enabled,
    set_telemetry_enabled,
    track_user_activity,
)

logger = logging.getLogger(__name__)

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
    password: str = Field(..., min_length=1)
    name: Optional[str] = None


class ProviderInfo(BaseModel):
    """Information about an authentication provider."""

    name: str
    display_name: str
    type: str  # 'oauth' or 'credentials'
    enabled: bool
    registration_enabled: Optional[bool] = None
    login_url: Optional[str] = None


class PasswordPolicyResponse(BaseModel):
    """Password policy exposed to frontend for client-side validation."""

    min_length: int
    max_length: int
    min_strength_score: int


class ProvidersResponse(BaseModel):
    """Response for /auth/providers endpoint."""

    providers: List[ProviderInfo]
    password_policy: PasswordPolicyResponse
    quick_start: bool = False


class VerifyEmailRequest(BaseModel):
    """Request body for email verification."""

    token: str


class ResendVerificationRequest(BaseModel):
    """Request body for resending verification email."""

    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    """Request body for forgot password."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request body for password reset."""

    token: str
    new_password: str = Field(..., min_length=1)


class MagicLinkRequest(BaseModel):
    """Request body for magic link login."""

    email: EmailStr


class TermsStatusResponse(BaseModel):
    """Response for terms acceptance lookup."""

    terms_accepted: bool
    has_prior_acceptance: bool = False


class MagicLinkVerifyRequest(BaseModel):
    """Request body for magic link verification."""

    token: str


class ExchangeCodeRequest(BaseModel):
    """Request body for exchanging an auth code for a session token."""

    code: str


class VerifyTokenRequest(BaseModel):
    """Request body for verifying a session token."""

    session_token: str
    return_to: str = "/home"


class RefreshTokenRequest(BaseModel):
    """Request body for refreshing an access token."""

    refresh_token: str


# =============================================================================
# Helper Functions
# =============================================================================

_LOCAL_HOSTNAMES = frozenset(("localhost", "127.0.0.1", "::1"))


def _get_api_base_url() -> str:
    return get_application_settings().api_base_url


def get_callback_url(request: Request, provider: Optional[str] = None) -> str:
    """Generate the OAuth callback URL from the configured API_BASE_URL.

    The one exception is loopback aliasing: when API_BASE_URL points at a
    loopback address, the OAuth session cookie is bound to whichever loopback
    alias the browser actually used (localhost vs 127.0.0.1 vs ::1), so the
    callback host is swapped to match — otherwise the cookie set before the
    redirect is not returned on the callback and state validation fails.

    The swap is gated on the *configured* host being loopback (a trusted,
    inherently-local value), and only ever selects another loopback alias, so
    the callback can never point off-box. For real (production) domains the
    request host is never trusted.
    """
    parsed = urlparse(_get_api_base_url().rstrip("/"))

    if parsed.hostname in _LOCAL_HOSTNAMES:
        # Loopback: follow the browser's alias (ignoring any non-loopback
        # request host) and keep the configured scheme — local dev is http.
        req_host = request.url.hostname
        host = req_host if req_host in _LOCAL_HOSTNAMES else parsed.hostname
        port = f":{parsed.port}" if parsed.port else ""
        base_url = f"{parsed.scheme}://{host}{port}"
    else:
        # Real domain: never trust the request host, and always use HTTPS
        # (guards a misconfigured http:// API_BASE_URL).
        base_url = f"https://{parsed.netloc}"

    return f"{base_url}/auth/callback"


def _get_frontend_url() -> str:
    """Get the frontend URL for building email links."""
    return get_frontend_settings().url


def _get_email_service():
    """Lazily import and return the email service."""
    from rhesis.backend.notifications.email.service import EmailService

    return EmailService()


# =============================================================================
# Provider Discovery Endpoint
# =============================================================================


def _resolve_org_by_id_or_slug(db: Session, org: str):
    """Resolve an organization by UUID or slug, returning ``None`` if not found.

    Both lookup keys live on core-managed columns of the
    :class:`~rhesis.backend.app.models.organization.Organization` model,
    so this helper has no EE-specific concerns. Slug comparison is
    case-insensitive to match the way SSO admins typically configure URLs.
    """
    from uuid import UUID as _UUID

    from rhesis.backend.app.models.organization import Organization

    try:
        _UUID(org)
        return db.query(Organization).filter(Organization.id == org).first()
    except ValueError:
        return db.query(Organization).filter(Organization.slug == org.lower()).first()


@router.get("/providers", response_model=ProvidersResponse)
async def get_providers(
    request: Request,
    org: Optional[str] = None,
    db: Session = Depends(get_db_session),
):
    """
    Get list of enabled authentication providers.

    Returns information about all configured and enabled authentication
    providers. The frontend uses this to dynamically render login options.
    Includes password policy (min/max length) for client-side validation.

    When ``org`` is provided, the organisation is resolved by UUID or
    slug and passed to any provider enrichers registered via
    :func:`~rhesis.backend.app.auth.provider_hooks.register_provider_enricher`.
    EE features (SSO, etc.) plug in at this point — core has no
    feature-specific knowledge here.
    """
    ProviderRegistry.initialize()
    providers = ProviderRegistry.get_provider_info()
    policy = get_password_policy()

    organization = None
    if org:
        # Failures in org lookup are non-fatal: enrichers run with
        # organization=None and produce a base provider list.
        try:
            organization = _resolve_org_by_id_or_slug(db, org)
        except Exception as exc:
            logger.warning(
                "Unexpected error resolving org %r for /auth/providers: %s", org, exc, exc_info=True
            )

    providers = apply_enrichers(providers, organization)

    return ProvidersResponse(
        providers=[ProviderInfo(**p) for p in providers],
        password_policy=PasswordPolicyResponse(
            min_length=policy.min_length,
            max_length=policy.max_length,
            min_strength_score=policy.min_strength_score,
        ),
        quick_start=is_quick_start_enabled(
            hostname=request.url.hostname,
            headers=dict(request.headers),
        ),
    )


@router.get("/terms-status", response_model=TermsStatusResponse)
@limiter.limit(AUTH_TERMS_STATUS_LIMIT)
async def get_terms_status(
    request: Request,
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    """
    Check whether the authenticated user has accepted the current T&C version.

    Used by onboarding step 0 to skip the checkbox for users who already accepted.
    """
    if user_has_accepted_current_terms(current_user):
        return TermsStatusResponse(
            terms_accepted=True,
            has_prior_acceptance=True,
        )
    return TermsStatusResponse(
        terms_accepted=False,
        has_prior_acceptance=user_has_prior_terms_acceptance(current_user),
    )


@router.post("/accept-terms")
async def accept_terms(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_current_user_or_token_without_context),
):
    """Record the authenticated user's acceptance of the current T&C version."""
    from rhesis.backend.app import crud
    from sqlalchemy.orm.attributes import flag_modified

    user = crud.get_user_by_id(db, current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    record_terms_acceptance(user)
    flag_modified(user, "user_settings")
    db.commit()
    return {"success": True, "terms_accepted": True}


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

    if not provider_name:
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

        # Capture values from pre-auth session before regeneration
        original_frontend = request.session.get("original_frontend")
        return_to = request.session.get("return_to", "/architect")

        # Set up session and create tokens
        clear_user_logout(str(user.id))
        session_token = create_session_token(user)
        refresh_tok = create_refresh_token(db, str(user.id))
        db.commit()

        # Regenerate session to prevent session fixation
        regenerate_session(request, {"user_id": str(user.id)})
        # Restore redirect context for build_redirect_url
        if original_frontend:
            request.session["original_frontend"] = original_frontend
        request.session["return_to"] = return_to

        # Track login activity
        if is_telemetry_enabled():
            set_telemetry_enabled(
                enabled=True,
                user_id=str(user.id),
                org_id=(str(user.organization_id) if user.organization_id else None),
            )
            track_user_activity(
                event_type="login",
                session_id=request.session.get("_id"),
                login_method="oauth",
                auth_provider=provider_name,
            )

        # Determine redirect URL
        redirect_url = await build_redirect_url(request, session_token, refresh_tok)
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
@limiter.limit(AUTH_LOGIN_EMAIL_LIMIT)
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

        # Set up session and create tokens. The refresh token is wrapped
        # in a short-lived, single-use auth code so it never reaches the
        # browser: the client exchanges the code via NextAuth server-side.
        request.session["user_id"] = str(user.id)
        clear_user_logout(str(user.id))
        access_token = create_session_token(user)
        refresh_tok = create_refresh_token(db, str(user.id))
        db.commit()
        auth_code = await create_auth_code(access_token, refresh_tok)

        # Track login activity
        if is_telemetry_enabled():
            set_telemetry_enabled(
                enabled=True,
                user_id=str(user.id),
                org_id=(str(user.organization_id) if user.organization_id else None),
            )
            track_user_activity(
                event_type="login",
                session_id=request.session.get("_id"),
                login_method="email",
                auth_provider="email",
            )

        return {
            "success": True,
            "auth_code": auth_code,
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
@limiter.limit(AUTH_REGISTER_LIMIT)
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

        # The user was already created in register(), so look them up
        from rhesis.backend.app import crud

        user = crud.get_user_by_email(db, body.email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User creation failed",
            )

        # Set up session and create tokens. Refresh token wrapped in a
        # single-use auth code (see /auth/login/email) so it stays out of
        # the browser.
        request.session["user_id"] = str(user.id)
        clear_user_logout(str(user.id))
        access_token = create_session_token(user)
        refresh_tok = create_refresh_token(db, str(user.id))
        db.commit()
        auth_code = await create_auth_code(access_token, refresh_tok)

        # Send welcome email (best-effort)
        _send_welcome_email(user)

        # Send verification email (best-effort)
        try:
            token = create_email_verification_token(str(user.id), user.email)
            frontend_url = _get_frontend_url()
            verification_url = f"{frontend_url}/auth/verify-email?token={token}"
            email_service = _get_email_service()
            email_service.send_verification_email(
                recipient_email=user.email,
                recipient_name=user.name,
                verification_url=verification_url,
            )
        except Exception as email_err:
            logger.warning(f"Failed to send verification email: {email_err}")

        # Track registration activity
        if is_telemetry_enabled():
            set_telemetry_enabled(
                enabled=True,
                user_id=str(user.id),
                org_id=(str(user.organization_id) if user.organization_id else None),
            )
            track_user_activity(
                event_type="registration",
                session_id=request.session.get("_id"),
                login_method="email",
                auth_provider="email",
            )

        return {
            "success": True,
            "auth_code": auth_code,
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
            detail="Registration failed. Please try again.",
        )


# =============================================================================
# Email Verification Endpoints
# =============================================================================


@router.post("/verify-email")
async def verify_email(
    body: VerifyEmailRequest,
    db: Session = Depends(get_db_session),
):
    """
    Verify a user's email address using the token from the verification
    email.
    """
    from rhesis.backend.app import crud

    payload = verify_email_flow_token(body.token, "email_verification")
    user = crud.get_user_by_email(db, payload["email"])

    # Enumeration-safe: return success even if user no longer exists
    if not user:
        return {
            "success": True,
            "message": "Email verified successfully",
        }

    if not user.is_email_verified:
        user.is_email_verified = True
        logger.info("Email verified for user: %s", redact_email(user.email))

    # Return a single-use auth code so the frontend can establish a
    # session without the refresh token ever touching the browser.
    access_token = create_session_token(user)
    refresh_tok = create_refresh_token(db, str(user.id))
    db.commit()
    auth_code = await create_auth_code(access_token, refresh_tok)

    return {
        "success": True,
        "message": "Email verified successfully",
        "auth_code": auth_code,
    }


@router.post("/resend-verification")
@limiter.limit(AUTH_RESEND_VERIFICATION_LIMIT)
async def resend_verification(
    request: Request,
    body: ResendVerificationRequest,
    db: Session = Depends(get_db_session),
):
    """
    Resend the verification email. Always returns 200 to prevent
    email enumeration.
    """
    from rhesis.backend.app import crud

    user = crud.get_user_by_email(db, body.email)

    if user and not user.is_email_verified:
        try:
            token = create_email_verification_token(str(user.id), user.email)
            frontend_url = _get_frontend_url()
            verification_url = f"{frontend_url}/auth/verify-email?token={token}"
            email_service = _get_email_service()
            email_service.send_verification_email(
                recipient_email=user.email,
                recipient_name=user.name,
                verification_url=verification_url,
            )
        except Exception as e:
            logger.warning(f"Failed to resend verification email: {e}")

    # Always return success to prevent email enumeration
    return {
        "success": True,
        "message": ("If an account exists with that email, a verification link has been sent."),
    }


# =============================================================================
# Password Reset Endpoints
# =============================================================================


@router.post("/forgot-password")
@limiter.limit(AUTH_FORGOT_PASSWORD_LIMIT)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db_session),
):
    """
    Request a password reset email. Always returns 200 to prevent
    email enumeration.
    """
    from rhesis.backend.app import crud

    user = crud.get_user_by_email(db, body.email)

    if user:
        try:
            token = create_password_reset_token(str(user.id), user.email)
            frontend_url = _get_frontend_url()
            reset_url = f"{frontend_url}/auth/reset-password?token={token}"
            email_service = _get_email_service()
            email_service.send_password_reset_email(
                recipient_email=user.email,
                recipient_name=user.name,
                reset_url=reset_url,
            )
            logger.info(
                "Password reset email sent to: %s",
                redact_email(user.email),
            )
        except Exception as e:
            logger.warning(f"Failed to send password reset email: {e}")

    # Always return success to prevent email enumeration
    return {
        "success": True,
        "message": ("If an account exists with that email, a password reset link has been sent."),
    }


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db_session),
):
    """
    Reset a user's password using the token from the reset email.
    Token is single-use: once used, it cannot be used again.
    """
    from rhesis.backend.app import crud
    from rhesis.backend.app.utils.encryption import hash_password

    payload = verify_email_flow_token(body.token, "password_reset")
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    ttl_seconds = PASSWORD_RESET_EXPIRE_MINUTES * 60
    try:
        claimed = await claim_token_jti(jti, ttl_seconds)
    except TokenStoreUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        )
    if not claimed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token already used or expired",
        )

    user = crud.get_user_by_email(db, payload["email"])

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    await validate_password(
        body.new_password,
        context={"email": user.email, "name": user.name or ""},
    )
    user.password_hash = hash_password(body.new_password)
    # Preserve original provider_type — setting a password is additive,
    # not a provider migration. Users can log in via either method.
    if not user.provider_type:
        user.provider_type = AuthProviderType.EMAIL
    db.commit()

    logger.info("Password reset for user: %s", redact_email(user.email))

    return {
        "success": True,
        "message": "Password has been reset successfully",
    }


# =============================================================================
# Magic Link Endpoints
# =============================================================================

_MAGIC_LINK_SUCCESS_RESPONSE = {
    "success": True,
    "message": "A sign-in link has been sent to your email.",
}


@router.post("/magic-link")
@limiter.limit(AUTH_MAGIC_LINK_LIMIT)
async def request_magic_link(
    request: Request,
    body: MagicLinkRequest,
    db: Session = Depends(get_db_session),
):
    """
    Send a magic link email. Creates a new account if the email
    doesn't exist yet (unified sign-in / sign-up flow).
    Always returns 200 to prevent email enumeration.
    """
    from rhesis.backend.app import crud
    from rhesis.backend.app.schemas.user import UserCreate

    user = crud.get_user_by_email(db, body.email)
    is_new_user = False

    if not user:
        try:
            user_data = UserCreate(
                email=body.email,
                provider_type=AuthProviderType.EMAIL,
                is_email_verified=False,
                is_active=True,
            )
            user = crud.create_user(db, user_data)
            db.commit()
            db.refresh(user)
            is_new_user = True
            logger.info(
                "New user created via magic link: %s",
                redact_email(body.email),
            )
        except Exception as e:
            logger.warning(f"Failed to create user for magic link: {e}")
            return _MAGIC_LINK_SUCCESS_RESPONSE

    try:
        token = create_magic_link_token(str(user.id), user.email)
        frontend_url = _get_frontend_url()
        magic_link_url = f"{frontend_url}/auth/magic-link?token={token}"
        email_service = _get_email_service()
        email_service.send_magic_link_email(
            recipient_email=user.email,
            recipient_name=user.name,
            magic_link_url=magic_link_url,
            is_new_user=is_new_user,
        )
        logger.info(
            "Magic link email sent to: %s",
            redact_email(user.email),
        )
    except Exception as e:
        logger.warning(f"Failed to send magic link email: {e}")

    # Send welcome email for newly created accounts (best-effort)
    if is_new_user:
        _send_welcome_email(user)

    return _MAGIC_LINK_SUCCESS_RESPONSE


@router.post("/magic-link/verify")
async def verify_magic_link(
    request: Request,
    body: MagicLinkVerifyRequest,
    db: Session = Depends(get_db_session),
):
    """
    Verify a magic link token and return a session token.
    Token is single-use: once used, it cannot be used again.
    """
    from rhesis.backend.app import crud

    payload = verify_email_flow_token(body.token, "magic_link")
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid magic link",
        )

    ttl_seconds = MAGIC_LINK_EXPIRE_MINUTES * 60
    try:
        claimed = await claim_token_jti(jti, ttl_seconds)
    except TokenStoreUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        )
    if not claimed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link already used or expired",
        )

    user = crud.get_user_by_email(db, payload["email"])

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid magic link",
        )

    # Mark email as verified (user clicked a link in their email)
    if not user.is_email_verified:
        user.is_email_verified = True

    # Update last login and stamp first org join when applicable
    from datetime import datetime, timezone

    current_time = datetime.now(timezone.utc)
    user.last_login_at = current_time
    mark_user_joined_if_needed(user, when=current_time)
    db.commit()

    # Set up session and create tokens. Refresh token wrapped in a
    # single-use auth code so it stays out of the browser.
    request.session["user_id"] = str(user.id)
    clear_user_logout(str(user.id))
    access_token = create_session_token(user)
    refresh_tok = create_refresh_token(db, str(user.id))
    db.commit()
    auth_code = await create_auth_code(access_token, refresh_tok)

    # Track login activity
    if is_telemetry_enabled():
        set_telemetry_enabled(
            enabled=True,
            user_id=str(user.id),
            org_id=(str(user.organization_id) if user.organization_id else None),
        )
        track_user_activity(
            event_type="login",
            session_id=request.session.get("_id"),
            login_method="magic_link",
            auth_provider="email",
        )

    return {
        "success": True,
        "auth_code": auth_code,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "organization_id": (str(user.organization_id) if user.organization_id else None),
        },
    }


# =============================================================================
# Auth Code Exchange Endpoint
# =============================================================================


@router.post("/exchange-code")
async def exchange_code(body: ExchangeCodeRequest):
    """
    Exchange a short-lived auth code for access + refresh tokens.

    Used by the frontend after OAuth callback redirect.
    The redirect URL contains a 60-second auth code (JWT)
    instead of the long-lived tokens, limiting exposure
    in browser history and server logs.
    """
    tokens = await verify_auth_code(body.code)
    return tokens


# =============================================================================
# Token Refresh Endpoint
# =============================================================================


#: Single response detail used for every 401 emitted by /auth/refresh.
#: We deliberately do not vary the string by failure reason because the
#: variants ("token not found" / "token expired" / "reuse detected" /
#: "user inactive" / "wrong client secret") would each be an oracle a
#: caller with a stolen refresh token could probe to learn whether the
#: token ever existed, whether they tripped reuse detection, etc.
#: Distinct reasons are still recorded in structured logs and the audit
#: trail; only the HTTP body is uniform.
_REFRESH_INVALID_DETAIL = "Invalid refresh token"


def _refresh_invalid() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_REFRESH_INVALID_DETAIL,
    )


@router.post("/refresh")
async def refresh_tokens(
    body: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    """Exchange a valid refresh token for a fresh access token.

    The refresh behaviour depends on the token's client binding:

    - **UI / SSO tokens** (``client_id`` IS NULL) are **not rotated**.
      A fresh short-lived session JWT is minted and the *same* refresh
      token is returned with its expiry slid forward. Browser sessions
      run through NextAuth, whose refresh runs inside Next.js React
      Server Component renders that cannot persist a rotated cookie;
      rotating there revoked the in-use token and forced spurious
      logouts. A stable token keeps refresh idempotent under concurrent
      renders / tabs. It stays revocable on logout, honours the
      ``is_active`` kill switch below, and hard-expires after
      ``REFRESH_TOKEN_EXPIRE_DAYS`` of inactivity.

    - **Token-exchange tokens** (rows with a non-null ``client_id``)
      keep **per-use rotation with reuse detection** and additional
      checks (the confidential client persists the rotated token
      itself, so the NextAuth limitation does not apply):

      * HTTP Basic ``Authorization`` is **required** -- the same
        AuthClient that minted the refresh token must re-authenticate
        to use it. Without this, a stolen refresh token alone would be
        sufficient to mint new access tokens.
      * The Basic credential's client_id must match the refresh token
        row's ``client_id``. Mismatch is an attempted lateral move.
      * The minted access token preserves the original
        ``azp`` / ``aud`` / ``scope`` / ``epoch`` so that scope cannot
        escalate across rotation and revocation via ``token_epoch``
        keeps applying to refreshed tokens.

    The bound user MUST still be active regardless of path. A disabled
    user's refresh token is rejected even if everything else is valid --
    otherwise ``DELETE /users/{id}`` (or the soft-disable equivalent)
    would not actually cut access until the access token expired.

    Every 401 returns the same generic detail string regardless of the
    underlying reason; differentiating them in the response body would
    let a caller with a stolen token probe whether the token ever
    existed, whether they tripped reuse detection, etc. Detailed
    reasons go to structured logs and the audit stream.
    """
    from rhesis.backend.app import crud
    from rhesis.backend.app.auth.refresh_client_hook import (
        get_refresh_client_minter,
    )

    # ``verify_and_refresh_token`` raises HTTPException with variant
    # detail strings (kept for backward compatibility with other call
    # sites). For /auth/refresh we replace the response body with the
    # uniform "invalid" string while still letting the function's
    # structured logs capture the precise reason.
    try:
        token_row, refresh_to_return = verify_and_refresh_token(db, body.refresh_token)
    except HTTPException as exc:
        # Keep 503 / 5xx as-is (those aren't oracles); collapse 401s.
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            raise _refresh_invalid() from exc
        raise

    user = crud.get_user(db, str(token_row.user_id))
    if not user:
        # User vanished between mint and refresh (unusual; would
        # require the user to be hard-deleted). Same uniform 401.
        logger.warning(
            "Refresh: user %s for token family %s no longer exists",
            token_row.user_id,
            token_row.family_id,
        )
        raise _refresh_invalid()

    # is_active is the operator-facing kill switch. Honouring it on
    # refresh closes the gap between "admin disabled this user" and
    # "all of that user's sessions actually stop working".
    if not getattr(user, "is_active", True):
        logger.warning(
            "Refresh: rejected for inactive user %s (family %s)",
            token_row.user_id,
            token_row.family_id,
        )
        raise _refresh_invalid()

    # Token-exchange-issued tokens carry a client binding that the
    # refresh request MUST re-prove. The check itself lives in EE
    # (because AuthClient is an EE concept) and is invoked here via
    # a hook the EE bootstrap registers. UI / SSO refresh tokens
    # have NULL client_id and skip the hook entirely.
    if token_row.client_id is not None:
        minter = get_refresh_client_minter()
        if minter is None:
            # A token-exchange-issued refresh exists in the DB but the
            # EE module is not loaded -- inconsistent deployment state.
            # Fail closed with 503; do not silently fall back to the
            # unbound minter, which would erase the client binding.
            logger.error(
                "Refresh token client_id=%s presented but EE refresh hook "
                "is not registered; rejecting",
                token_row.client_id,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Token refresh temporarily unavailable",
            )
        try:
            access_token = minter(db, request, token_row, user)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_401_UNAUTHORIZED:
                raise _refresh_invalid() from exc
            raise
    else:
        access_token = create_session_token(user)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_to_return,
        "token_type": "bearer",
    }


# =============================================================================
# Session Management Endpoints
# =============================================================================


@router.get("/logout")
async def logout(
    request: Request,
    post_logout: bool = False,
    session_token: str = None,
    db: Session = Depends(get_db_session),
):
    """Log out the user and clear their session"""
    # Clear session data
    request.session.clear()

    # The browser never holds the access token (BFF pattern), so explicit
    # sign-outs arrive through the frontend proxy with the token in the
    # Authorization header instead of the query string. Fall back to it so
    # those logouts still revoke the refresh-token family.
    if not session_token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            session_token = auth_header[7:]

    # If session token is provided, invalidate sessions + refresh tokens
    if session_token:
        try:
            secret_key = get_secret_key()
            payload = verify_jwt_token(session_token, secret_key)
            user_info = payload.get("user", {})
            user_id = user_info.get("id")

            if user_id:
                logger.info(f"Logout called for user {user_id} via JWT token")

                # Invalidate all sessions and refresh tokens
                invalidate_user_sessions(user_id)
                revoke_all_for_user(db, user_id)
                db.commit()

                # Bust the permission cache so a re-login always gets fresh
                # permissions (role changes take effect immediately after next login).
                org_id = user_info.get("organization_id")
                if org_id:
                    from uuid import UUID as _UUID

                    from rhesis.backend.app.services.permission_cache import (
                        get_permission_cache,
                    )

                    try:
                        get_permission_cache().bust_user(_UUID(user_id), _UUID(org_id))
                    except Exception as cache_err:
                        logger.warning("Failed to bust permission cache on logout: %s", cache_err)

                # Track logout activity
                if is_telemetry_enabled():
                    org_id = user_info.get("organization_id")
                    set_telemetry_enabled(
                        enabled=True,
                        user_id=str(user_id),
                        org_id=str(org_id) if org_id else None,
                    )
                    track_user_activity(
                        event_type="logout",
                        session_id=request.session.get("_id"),
                    )

        except JWTError as e:
            logger.warning(f"Invalid session token during logout: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing logout: {str(e)}")

    # Create response with cookie clearing headers
    accept_header = request.headers.get("accept", "")
    frontend_url = get_frontend_settings().url

    # Check if this is an API call (from frontend middleware)
    if "application/json" in accept_header or "api" in request.url.path:
        response = JSONResponse(content={"success": True, "message": "Logged out successfully"})
    else:
        # Redirect to frontend home page
        return_to_url = frontend_url + "/"
        response = RedirectResponse(url=return_to_url)

    # Clear the backend SessionMiddleware cookie (host-only on the API origin).
    # NextAuth cookies live on the frontend host and are cleared there.
    # Emit both Secure and non-Secure clears so logout works regardless of
    # how the cookie was set (SessionMiddleware derives https_only from the
    # API_BASE_URL scheme via ApplicationSettings.secure_cookies). The
    # mismatched variant is a harmless no-op.
    for secure in (False, True):
        response.set_cookie(
            key="session",
            value="",
            max_age=0,
            expires=0,
            path="/",
            httponly=True,
            secure=secure,
            samesite="lax",
        )

    logger.info("Logout completed, cookies cleared")
    return response


@router.post("/verify")
async def verify_auth(
    request: Request,
    body: VerifyTokenRequest,
    secret_key: str = Depends(get_secret_key),
):
    """Verify JWT session token and return user info"""
    session_token = body.session_token
    return_to = body.return_to
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

        return {
            "authenticated": True,
            "user": payload["user"],
            "return_to": return_to,
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
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


# =============================================================================
# Demo and Quick Start Endpoints
# =============================================================================


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
        clear_user_logout(str(user.id))
        access_token = create_session_token(user)
        refresh_tok = create_refresh_token(db, str(user.id))
        db.commit()
        auth_code = await create_auth_code(access_token, refresh_tok)

        logger.info(
            "QUICK START MODE login successful for user: %s",
            redact_email(user.email),
        )

        if is_telemetry_enabled():
            set_telemetry_enabled(
                enabled=True,
                user_id=str(user.id),
                org_id=(str(user.organization_id) if user.organization_id else None),
            )
            track_user_activity(
                event_type="login",
                session_id=request.session.get("_id"),
                login_method="local_dev",
                auth_provider="local",
            )

        return {
            "success": True,
            "auth_code": auth_code,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "organization_id": (str(user.organization_id) if user.organization_id else None),
            },
            "message": ("QUICK START MODE login - Not for production use!"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QUICK START MODE login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"QUICK START MODE login failed: {str(e)}",
        )
