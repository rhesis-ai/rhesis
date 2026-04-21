"""SSO authentication and admin endpoints.

Contains:
- GET /auth/sso/{org_id} -- Initiates SSO login
- GET /auth/sso/callback -- Handles OIDC callback
- GET /organizations/{id}/sso -- Get SSO config (masked)
- PUT /organizations/{id}/sso -- Set/update SSO config
- DELETE /organizations/{id}/sso -- Remove SSO config
- POST /organizations/{id}/sso/test -- Test OIDC discovery
"""

import hashlib
import logging
import os
import secrets
from base64 import urlsafe_b64encode
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.providers.oidc import (
    OIDCProvider,
    verify_signed_state,
)
from rhesis.backend.app.auth.refresh_token_utils import create_refresh_token
from rhesis.backend.app.auth.session_invalidation import clear_user_logout
from rhesis.backend.app.auth.session_utils import regenerate_session
from rhesis.backend.app.auth.sso_audit import SSOAuditEvent, audit_log
from rhesis.backend.app.auth.sso_http_client import SSOHttpClient, SSRFError, is_dev_environment
from rhesis.backend.app.auth.sso_user_utils import SSOLoginError, find_or_create_sso_user
from rhesis.backend.app.auth.token_utils import create_session_token
from rhesis.backend.app.auth.url_utils import build_redirect_url
from rhesis.backend.app.dependencies import get_db_session
from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.schemas.sso_config import SSOConfig
from rhesis.backend.app.utils.encryption import (
    sso_decrypt,
    sso_encrypt,
)
from rhesis.backend.app.utils.rate_limit import (
    SSO_ADMIN_RATE_LIMIT,
    SSO_CALLBACK_RATE_LIMIT,
    SSO_LOGIN_RATE_LIMIT,
    SSO_TEST_CONNECTION_RATE_LIMIT,
    limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["SSO"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


# =============================================================================
# Helpers
# =============================================================================


def check_sso_available(organization: Optional[Organization] = None) -> bool:
    """Return ``True`` iff SSO is available (for ``organization`` if given).

    Thin wrapper around :meth:`FeatureRegistry.is_available`. Kept at
    this import path for backward compatibility with existing callers;
    licensing, runtime preconditions, and future per-org entitlements
    all flow through the registry now.
    """
    return FeatureRegistry.is_available(FeatureName.SSO, organization)


def _get_sso_config(organization: Organization) -> Optional[SSOConfig]:
    """Load and validate SSO config from an organization's JSON column."""
    if not organization.sso_config:
        return None
    try:
        config_data = dict(organization.sso_config)
        if "client_secret" in config_data and isinstance(
            config_data["client_secret"], str
        ):
            try:
                config_data["client_secret"] = sso_decrypt(
                    config_data["client_secret"]
                )
            except Exception:
                if is_dev_environment():
                    logger.warning(
                        "SSO client_secret decryption failed for org %s; "
                        "allowing plaintext fallback in local/test",
                        organization.id,
                    )
                else:
                    logger.error(
                        "SSO client_secret decryption failed for org %s; "
                        "config unusable (key rotation or corruption?)",
                        organization.id,
                    )
                    return None
        return SSOConfig(**config_data)
    except Exception as e:
        logger.error("Invalid SSO config for org %s: %s", organization.id, e)
        return None


def _get_org_or_404(db: Session, org_identifier: str) -> Organization:
    """Look up org by UUID or slug, raise uniform 404.

    Tries UUID first; if the identifier is not a valid UUID, falls back to
    slug lookup.  Returns the same generic 404 in all failure cases to
    prevent organization enumeration.
    """
    from uuid import UUID as _UUID

    org = None
    try:
        _UUID(org_identifier)
        org = (
            db.query(Organization)
            .filter(Organization.id == org_identifier)
            .first()
        )
    except ValueError:
        org = (
            db.query(Organization)
            .filter(Organization.slug == org_identifier.lower())
            .first()
        )

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not available",
        )
    return org


def _validate_return_to(return_to: Optional[str]) -> str:
    """Validate and sanitize the return_to parameter."""
    from urllib.parse import unquote

    if not return_to:
        return "/dashboard"

    # Decode percent-encoding before running blocklist checks to prevent
    # bypasses via %2f%2f, %6Aavascript:, etc.
    decoded = unquote(unquote(return_to))

    if not decoded.startswith("/"):
        return "/dashboard"

    blocked = ["//", "javascript:", "data:", "http:", "https:", "\\"]
    for pattern in blocked:
        if pattern in decoded.lower():
            return "/dashboard"

    return decoded


def _generate_pkce() -> tuple:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def _get_sso_callback_url(request: Request) -> str:
    """Build the SSO callback URL."""
    from rhesis.backend.app.routers.auth import is_running_locally

    rhesis_base_url = os.getenv("RHESIS_BASE_URL", "")

    if is_running_locally() and not rhesis_base_url:
        base_url = str(request.base_url).rstrip("/")
    elif rhesis_base_url:
        base_url = rhesis_base_url.rstrip("/")
    else:
        base_url = str(request.base_url).rstrip("/")

    return f"{base_url}/auth/sso/callback"


# =============================================================================
# SSO Auth Endpoints
# =============================================================================


@router.get("/auth/sso/callback")
@limiter.limit(SSO_CALLBACK_RATE_LIMIT)
async def sso_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: Optional[str] = None,
    db: Session = Depends(get_db_session),
):
    """Handle OIDC callback after IdP authentication."""
    error_redirect = f"{FRONTEND_URL}/auth/sso-error?error=login_failed"

    if error:
        logger.warning("SSO callback received error from IdP: %s", error)
        return RedirectResponse(url=error_redirect, status_code=302)

    if not code or not state:
        return RedirectResponse(url=error_redirect, status_code=302)

    # Validate signed state
    try:
        state_payload = verify_signed_state(state)
    except ValueError as e:
        logger.warning("SSO state validation failed: %s", e)
        return RedirectResponse(url=error_redirect, status_code=302)

    org_id = state_payload.get("org_id", "")
    state_nonce = state_payload.get("nonce", "")
    state_return_to = state_payload.get("return_to", "/dashboard")

    # Cross-check org_id from state against session (defense in depth)
    session_org_id = request.session.get("sso_org_id", "")
    if session_org_id and session_org_id != org_id:
        logger.warning(
            "SSO org_id mismatch: state=%s session=%s", org_id, session_org_id
        )
        return RedirectResponse(url=error_redirect, status_code=302)

    if not check_sso_available():
        return RedirectResponse(url=error_redirect, status_code=302)

    try:
        org = _get_org_or_404(db, org_id)
    except HTTPException:
        return RedirectResponse(url=error_redirect, status_code=302)

    sso_config = _get_sso_config(org)
    if not sso_config or not sso_config.enabled:
        return RedirectResponse(url=error_redirect, status_code=302)

    # Retrieve PKCE verifier and nonce from session
    code_verifier = request.session.get("sso_code_verifier", "")
    session_nonce = request.session.get("sso_nonce", "")

    if not code_verifier:
        logger.warning("SSO callback missing code_verifier in session")
        return RedirectResponse(url=error_redirect, status_code=302)

    redirect_uri = _get_sso_callback_url(request)

    # Authenticate with OIDC provider
    provider = OIDCProvider(sso_config)
    try:
        auth_user = await provider.authenticate(
            request,
            code=code,
            code_verifier=code_verifier,
            nonce=session_nonce or state_nonce,
            redirect_uri=redirect_uri,
        )
    except (ValueError, SSRFError) as e:
        logger.error("SSO authentication failed for org %s: %s", org_id, e)
        audit_log(
            SSOAuditEvent.LOGIN_FAILED,
            org_id,
            reason_code="authentication_failed",
        )
        return RedirectResponse(url=error_redirect, status_code=302)

    # Org-scoped user resolution
    try:
        user = find_or_create_sso_user(db, auth_user, org, sso_config)
    except SSOLoginError as e:
        audit_log(
            SSOAuditEvent.LOGIN_FAILED,
            org_id,
            email=auth_user.email,
            reason_code=e.reason_code,
        )
        return RedirectResponse(url=error_redirect, status_code=302)

    # Create tokens
    clear_user_logout(str(user.id))
    session_token = create_session_token(user)
    refresh_tok = create_refresh_token(db, str(user.id))
    db.commit()

    # Regenerate session (prevents session fixation)
    regenerate_session(request, {"user_id": str(user.id)})
    # Restore redirect context for build_redirect_url
    request.session["return_to"] = state_return_to

    audit_log(
        SSOAuditEvent.LOGIN_SUCCESS,
        org_id,
        email=auth_user.email,
    )

    redirect_url = build_redirect_url(request, session_token, refresh_tok)
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/auth/sso/{org_id}")
@limiter.limit(SSO_LOGIN_RATE_LIMIT)
async def sso_login(
    request: Request,
    org_id: str,
    return_to: Optional[str] = None,
    db: Session = Depends(get_db_session),
):
    """Initiate SSO login for an organization."""
    if not check_sso_available():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not available",
        )

    org = _get_org_or_404(db, org_id)
    sso_config = _get_sso_config(org)

    if not sso_config or not sso_config.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not available",
        )

    return_to = _validate_return_to(return_to)

    audit_log(SSOAuditEvent.LOGIN_INITIATED, org_id)

    # Generate PKCE pair
    code_verifier, code_challenge = _generate_pkce()

    # Generate nonce
    nonce = secrets.token_urlsafe(32)

    # Store in session for callback verification
    request.session["sso_code_verifier"] = code_verifier
    request.session["sso_org_id"] = org_id
    request.session["sso_nonce"] = nonce
    # Preserve original frontend and return_to for build_redirect_url
    original_frontend = request.headers.get("referer", "")
    if original_frontend:
        request.session["original_frontend"] = original_frontend
    request.session["return_to"] = return_to

    redirect_uri = _get_sso_callback_url(request)

    provider = OIDCProvider(sso_config)
    auth_url = await provider.get_authorization_url(
        request,
        redirect_uri=redirect_uri,
        org_id=org_id,
        code_verifier=code_verifier,
        code_challenge=code_challenge,
        nonce=nonce,
        return_to=return_to,
    )

    return RedirectResponse(url=auth_url, status_code=302)


# =============================================================================
# SSO Admin API
# =============================================================================


class SSOConfigRequest(BaseModel):
    enabled: bool = False
    provider_type: str = "oidc"
    issuer_url: str
    client_id: str
    client_secret: Optional[str] = None
    scopes: str = "openid email profile"
    auto_provision_users: bool = False
    allowed_domains: Optional[List[str]] = None
    allowed_auth_methods: Optional[List[str]] = None
    slug: Optional[str] = None


class SSOTestResponse(BaseModel):
    success: bool
    message: str


async def _require_org_admin(request: Request, org_id: str):
    """Verify the current user is an admin of the specified org.

    Supports both session cookies and Bearer token authentication
    to work with the frontend API client.
    """
    from rhesis.backend.app.auth.user_utils import (
        bearer_scheme,
        get_authenticated_user_with_context,
        get_secret_key,
    )

    credentials = await bearer_scheme(request)
    secret_key = get_secret_key()
    user = await get_authenticated_user_with_context(
        request, credentials, secret_key
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Superusers can manage any org's SSO
    if getattr(user, "is_superuser", False):
        return user

    if str(user.organization_id) != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this organization's SSO",
        )

    return user


@router.get("/organizations/{org_id}/sso")
@limiter.limit(SSO_ADMIN_RATE_LIMIT)
async def get_sso_config(
    request: Request,
    org_id: str,
    db: Session = Depends(get_db_session),
):
    """Get SSO configuration for an organization (client_secret masked)."""
    user = await _require_org_admin(request, org_id)

    if not check_sso_available():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not available",
        )

    org = _get_org_or_404(db, org_id)
    sso_config = _get_sso_config(org)

    if not sso_config:
        return None

    result = sso_config.masked_dict()
    result["slug"] = org.slug or ""
    if org.slug:
        result["login_url"] = f"/auth/sso/{org.slug}"
    else:
        result["login_url"] = f"/auth/sso/{org.id}"
    return result


@router.put("/organizations/{org_id}/sso")
@limiter.limit(SSO_ADMIN_RATE_LIMIT)
async def update_sso_config(
    request: Request,
    org_id: str,
    body: SSOConfigRequest,
    db: Session = Depends(get_db_session),
):
    """Set or update SSO configuration for an organization."""
    user = await _require_org_admin(request, org_id)

    if not check_sso_available():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not available",
        )

    # SELECT FOR UPDATE to prevent concurrent writes
    org = (
        db.query(Organization)
        .filter(Organization.id == org_id)
        .with_for_update()
        .first()
    )
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not available",
        )

    # Determine the client_secret to use for validation and storage.
    # If the caller omitted or sent empty client_secret, preserve
    # the existing encrypted secret from the database.
    new_secret_provided = bool(body.client_secret)
    if new_secret_provided:
        plaintext_secret = body.client_secret
    else:
        if org.sso_config and org.sso_config.get("client_secret"):
            existing_config = _get_sso_config(org)
            if not existing_config:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Existing SSO config is corrupted; "
                    "please provide client_secret again",
                )
            plaintext_secret = existing_config.get_secret_value()
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="client_secret is required for initial SSO configuration",
            )

    # Validate via SSOConfig (triggers all field validators)
    try:
        validated = SSOConfig(
            enabled=body.enabled,
            provider_type=body.provider_type,
            issuer_url=body.issuer_url,
            client_id=body.client_id,
            client_secret=SecretStr(plaintext_secret),
            scopes=body.scopes,
            auto_provision_users=body.auto_provision_users,
            allowed_domains=body.allowed_domains,
            allowed_auth_methods=body.allowed_auth_methods,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    # Encrypt client_secret before storage
    encrypted_secret = sso_encrypt(plaintext_secret)

    config_dict = validated.model_dump()
    config_dict["client_secret"] = encrypted_secret

    # Handle slug update
    if body.slug is not None:
        import re

        slug_val = body.slug.strip().lower() if body.slug else None
        if slug_val == "":
            slug_val = None
        if slug_val:
            slug_re = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
            if not slug_re.match(slug_val) or "--" in slug_val:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Slug must be 3-50 characters, lowercase "
                    "alphanumeric and hyphens, no consecutive hyphens",
                )
            existing = (
                db.query(Organization)
                .filter(Organization.slug == slug_val, Organization.id != org.id)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This slug is already taken",
                )

    is_new = org.sso_config is None
    org.sso_config = config_dict
    if body.slug is not None:
        org.slug = slug_val
    db.commit()
    db.refresh(org)

    event = SSOAuditEvent.CONFIG_CREATED if is_new else SSOAuditEvent.CONFIG_UPDATED
    audit_log(
        event,
        org_id,
        actor_id=str(user.id),
        details={
            "fields_changed": [
                k for k in config_dict if k != "client_secret"
            ]
        },
    )

    result = validated.masked_dict()
    result["slug"] = org.slug or ""
    if org.slug:
        result["login_url"] = f"/auth/sso/{org.slug}"
    else:
        result["login_url"] = f"/auth/sso/{org.id}"
    return result


@router.delete("/organizations/{org_id}/sso")
@limiter.limit(SSO_ADMIN_RATE_LIMIT)
async def delete_sso_config(
    request: Request,
    org_id: str,
    db: Session = Depends(get_db_session),
):
    """Remove SSO configuration for an organization.

    Unlike get/update, delete intentionally works even when SSO encryption
    is unavailable so that admins can always clean up broken configurations.
    """
    user = await _require_org_admin(request, org_id)

    org = _get_org_or_404(db, org_id)
    org.sso_config = None
    org.slug = None
    db.commit()

    audit_log(
        SSOAuditEvent.CONFIG_DELETED,
        org_id,
        actor_id=str(user.id),
    )

    return {"status": "deleted"}


@router.post("/organizations/{org_id}/sso/test")
@limiter.limit(SSO_TEST_CONNECTION_RATE_LIMIT)
async def test_sso_connection(
    request: Request,
    org_id: str,
    db: Session = Depends(get_db_session),
):
    """Test OIDC discovery for an org's SSO configuration."""
    user = await _require_org_admin(request, org_id)

    if not check_sso_available():
        return SSOTestResponse(success=False, message="SSO is not available")

    org = _get_org_or_404(db, org_id)
    sso_config = _get_sso_config(org)

    if not sso_config:
        return SSOTestResponse(success=False, message="SSO is not configured")

    http_client = SSOHttpClient()
    discovery_url = f"{sso_config.issuer_url}/.well-known/openid-configuration"

    try:
        resp = await http_client.get(discovery_url)
        resp.raise_for_status()
        metadata = resp.json()

        required_keys = [
            "authorization_endpoint",
            "token_endpoint",
            "jwks_uri",
        ]
        missing = [k for k in required_keys if k not in metadata]
        if missing:
            logger.warning(
                "SSO test for org %s: missing metadata keys: %s",
                org_id,
                missing,
            )
            return SSOTestResponse(
                success=False,
                message="OIDC discovery incomplete",
            )

        return SSOTestResponse(
            success=True,
            message="OIDC discovery successful",
        )

    except SSRFError:
        logger.warning("SSO test blocked for org %s: SSRF protection", org_id)
        return SSOTestResponse(
            success=False,
            message="Connection blocked by security policy",
        )
    except Exception as e:
        logger.error(
            "SSO test failed for org %s: %s", org_id, type(e).__name__
        )
        return SSOTestResponse(
            success=False,
            message="Connection failed",
        )
