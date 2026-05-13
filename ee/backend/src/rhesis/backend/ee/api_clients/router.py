"""Org-scoped REST endpoints for managing :class:`AuthClient` rows.

URL surface (no ``/sso/`` prefix; this is its own EE feature):

- ``POST   /organizations/{org_id}/auth-clients``        -- create + return one-shot secret
- ``GET    /organizations/{org_id}/auth-clients``        -- list (no secrets)
- ``GET    /organizations/{org_id}/auth-clients/{id}``   -- single row (no secret)
- ``POST   /organizations/{org_id}/auth-clients/{id}/rotate``   -- rotate secret + epoch
- ``POST   /organizations/{org_id}/auth-clients/{id}/disable``  -- soft-disable
- ``POST   /organizations/{org_id}/auth-clients/{id}/enable``   -- re-enable
- ``DELETE /organizations/{org_id}/auth-clients/{id}``    -- only when disabled

Cross-org isolation
-------------------
A request from org A asking for a client owned by org B returns 404,
**never** 403. This is the same pattern used by the SSO admin
endpoints: a 403 would tell an attacker that the resource exists, just
in someone else's tenant. The 404 is uniform whether the row does not
exist at all or belongs to a different org.

Permission model
----------------
Reuses the org-admin dependency from the SSO router (whoever can
manage ``SSOConfig`` for an org can manage that org's ``AuthClient``s).
No new role.

Slug precondition (S11)
-----------------------
Creating an ``AuthClient`` for an org with ``slug IS NULL`` returns
409 with a clear message instructing the admin to set the slug first.
The audience parameter at the exchange endpoint requires a slug
(``audience=rhesis:org:<slug>``); without one the resulting client is
unusable. Failing at create time means the misconfiguration surfaces
in the admin's session, not in a confusing ``invalid_target`` from a
production exchange call.

Audit
-----
Every state-changing route emits an :class:`AuthClientLifecycleEvent`
with the acting user's ID, the request IP, and the user agent. The
audit module's allowlist is what prevents the plaintext secret from
ever reaching the log buffer (only an 8-char prefix of the secret
hash is logged, for correlation).
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app.dependencies import get_db_session
from rhesis.backend.app.features import FeatureName
from rhesis.backend.app.auth.feature_gates import require_feature
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.utils.rate_limit import limiter
from rhesis.backend.ee.api_clients.audit import (
    AuthClientLifecycleEvent,
    auth_client_audit_log,
)
from rhesis.backend.ee.api_clients.clients import (
    AuthClient,
    generate_client_secret,
    get_client_by_id_for_org,
    hash_client_secret,
)
from rhesis.backend.ee.api_clients.schemas import (
    AuthClientCreate,
    AuthClientCreatedResponse,
    AuthClientResponse,
)
from rhesis.backend.ee.sso.rate_limits import SSO_ADMIN_RATE_LIMIT

logger = logging.getLogger(__name__)

router = APIRouter(tags=["API Clients"])


# ---------------------------------------------------------------------------
# Authn / authz helpers (mirror SSO router conventions)
# ---------------------------------------------------------------------------


async def _require_org_admin_for(request: Request, org_id: str):
    """Resolve the current user and assert they may manage *org_id*'s clients.

    Mirrors the SSO router's ``_require_org_admin`` so that the
    permission story for "API Clients" is identical to "SSO": an org's
    admin manages both. Cross-org access by a non-superuser returns
    404 (not 403) to avoid leaking which orgs exist.
    """
    from rhesis.backend.app.auth.user_utils import (
        bearer_scheme,
        get_authenticated_user_with_context,
        get_secret_key,
    )

    credentials = await bearer_scheme(request)
    user = await get_authenticated_user_with_context(
        request, credentials, get_secret_key()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    if getattr(user, "is_superuser", False):
        return user

    if str(user.organization_id) != org_id:
        # 404, not 403, to keep cross-org enumeration impossible.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    return user


def _get_org_or_404(db: Session, org_id: str) -> Organization:
    """Resolve an Organization by UUID; uniform 404 on any failure."""
    try:
        UUID(org_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    return org


def _get_client_or_404(db: Session, org_id: str, client_pk: str) -> AuthClient:
    """Look up an AuthClient by primary key, scoped to *org_id*.

    Both "wrong org" and "no such row" return 404 with the same body
    so an attacker cannot distinguish the two via response.
    """
    try:
        UUID(client_pk)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    row: Optional[AuthClient] = (
        db.query(AuthClient)
        .filter(
            AuthClient.id == client_pk,
            AuthClient.organization_id == org_id,
            AuthClient.deleted_at.is_(None),
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    return row


def _request_ip(request: Request) -> Optional[str]:
    """Best-effort source IP for the audit trail.

    Routes through the existing trusted-proxy-aware extractor in
    ``utils.rate_limit`` so the audit IP and the rate-limit IP agree.
    """
    from rhesis.backend.app.utils.rate_limit import get_real_ip

    try:
        return get_real_ip(request)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/organizations/{org_id}/auth-clients",
    response_model=AuthClientCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(SSO_ADMIN_RATE_LIMIT)
async def create_auth_client(
    request: Request,
    org_id: str,
    body: AuthClientCreate,
    db: Session = Depends(get_db_session),
    _gate: object = Depends(require_feature(FeatureName.API_CLIENTS)),
):
    """Create a new :class:`AuthClient`.

    The plaintext ``client_secret`` is returned once in the response
    body. There is no other code path that recovers it.
    """
    user = await _require_org_admin_for(request, org_id)
    org = _get_org_or_404(db, org_id)

    if not org.slug:
        # S11 -- the audience parameter at /auth/token-exchange requires
        # a slug. Without one the client we'd create is unreachable.
        # Surface the misconfiguration here instead of producing a
        # confusing invalid_target later.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Organization has no slug; set one before creating an "
                "API client (the token-exchange audience uses the slug)."
            ),
        )

    plaintext_secret = generate_client_secret()
    secret_hash = hash_client_secret(plaintext_secret)

    row = AuthClient(
        organization_id=org.id,
        client_id=body.client_id,
        client_secret_hash=secret_hash,
        expected_subject_azp=body.expected_subject_azp,
        expected_subject_audience=body.expected_subject_audience,
        name=body.name,
        allowed_scopes=list(body.allowed_scopes),
        default_scope=body.default_scope,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Same body for both "duplicate client_id" and "duplicate name"
        # so a probe cannot enumerate which constraint fired.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An API client with that identifier or name already "
                "exists in this organization."
            ),
        )
    db.refresh(row)

    auth_client_audit_log(
        AuthClientLifecycleEvent.CREATED,
        org_id=str(org.id),
        client_id=row.client_id,
        actor_id=str(user.id),
        ip=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
        secret_hash_for_correlation=secret_hash,
    )

    response = AuthClientResponse.model_validate(row)
    return AuthClientCreatedResponse(**response.model_dump(), client_secret=plaintext_secret)


@router.get(
    "/organizations/{org_id}/auth-clients",
    response_model=List[AuthClientResponse],
)
@limiter.limit(SSO_ADMIN_RATE_LIMIT)
async def list_auth_clients(
    request: Request,
    org_id: str,
    db: Session = Depends(get_db_session),
    _gate: object = Depends(require_feature(FeatureName.API_CLIENTS)),
):
    """List :class:`AuthClient` rows for the org. No secret material."""
    await _require_org_admin_for(request, org_id)
    _get_org_or_404(db, org_id)

    rows = (
        db.query(AuthClient)
        .filter(
            AuthClient.organization_id == org_id,
            AuthClient.deleted_at.is_(None),
        )
        .order_by(AuthClient.created_at.desc())
        .all()
    )
    return [AuthClientResponse.model_validate(r) for r in rows]


@router.get(
    "/organizations/{org_id}/auth-clients/{client_pk}",
    response_model=AuthClientResponse,
)
@limiter.limit(SSO_ADMIN_RATE_LIMIT)
async def get_auth_client(
    request: Request,
    org_id: str,
    client_pk: str,
    db: Session = Depends(get_db_session),
    _gate: object = Depends(require_feature(FeatureName.API_CLIENTS)),
):
    await _require_org_admin_for(request, org_id)
    _get_org_or_404(db, org_id)
    row = _get_client_or_404(db, org_id, client_pk)
    return AuthClientResponse.model_validate(row)


@router.post(
    "/organizations/{org_id}/auth-clients/{client_pk}/rotate",
    response_model=AuthClientCreatedResponse,
)
@limiter.limit(SSO_ADMIN_RATE_LIMIT)
async def rotate_auth_client_secret(
    request: Request,
    org_id: str,
    client_pk: str,
    db: Session = Depends(get_db_session),
    _gate: object = Depends(require_feature(FeatureName.API_CLIENTS)),
):
    """Rotate the secret. Old hash is overwritten immediately (no overlap).

    Also bumps ``token_epoch`` to the rotation instant, which (via the
    ``iat >= epoch`` check in :func:`verify_jwt_token`) invalidates
    every Rhesis JWT issued before the rotation. That is the only
    coarse-revocation lever in v1; per-token revocation lands later.
    """
    from datetime import datetime, timezone

    user = await _require_org_admin_for(request, org_id)
    _get_org_or_404(db, org_id)
    row = _get_client_or_404(db, org_id, client_pk)

    plaintext_secret = generate_client_secret()
    new_hash = hash_client_secret(plaintext_secret)
    row.client_secret_hash = new_hash
    # Bumping the epoch invalidates every previously-issued access
    # token for this client; that's why rotate is the recommended
    # incident-response action when a secret is suspected compromised.
    row.token_epoch = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)

    auth_client_audit_log(
        AuthClientLifecycleEvent.ROTATED,
        org_id=str(row.organization_id),
        client_id=row.client_id,
        actor_id=str(user.id),
        ip=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
        secret_hash_for_correlation=new_hash,
    )

    response = AuthClientResponse.model_validate(row)
    return AuthClientCreatedResponse(
        **response.model_dump(),
        client_secret=plaintext_secret,
    )


@router.post(
    "/organizations/{org_id}/auth-clients/{client_pk}/disable",
    response_model=AuthClientResponse,
)
@limiter.limit(SSO_ADMIN_RATE_LIMIT)
async def disable_auth_client(
    request: Request,
    org_id: str,
    client_pk: str,
    db: Session = Depends(get_db_session),
    _gate: object = Depends(require_feature(FeatureName.API_CLIENTS)),
):
    """Soft-disable. Token exchange and refresh both reject ``invalid_client``."""
    user = await _require_org_admin_for(request, org_id)
    _get_org_or_404(db, org_id)
    row = _get_client_or_404(db, org_id, client_pk)

    if not row.disabled:
        row.disabled = True
        db.commit()
        db.refresh(row)
        auth_client_audit_log(
            AuthClientLifecycleEvent.DISABLED,
            org_id=str(row.organization_id),
            client_id=row.client_id,
            actor_id=str(user.id),
            ip=_request_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

    return AuthClientResponse.model_validate(row)


@router.post(
    "/organizations/{org_id}/auth-clients/{client_pk}/enable",
    response_model=AuthClientResponse,
)
@limiter.limit(SSO_ADMIN_RATE_LIMIT)
async def enable_auth_client(
    request: Request,
    org_id: str,
    client_pk: str,
    db: Session = Depends(get_db_session),
    _gate: object = Depends(require_feature(FeatureName.API_CLIENTS)),
):
    """Re-enable a disabled client."""
    user = await _require_org_admin_for(request, org_id)
    _get_org_or_404(db, org_id)
    row = _get_client_or_404(db, org_id, client_pk)

    if row.disabled:
        row.disabled = False
        db.commit()
        db.refresh(row)
        auth_client_audit_log(
            AuthClientLifecycleEvent.ENABLED,
            org_id=str(row.organization_id),
            client_id=row.client_id,
            actor_id=str(user.id),
            ip=_request_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

    return AuthClientResponse.model_validate(row)


@router.delete(
    "/organizations/{org_id}/auth-clients/{client_pk}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit(SSO_ADMIN_RATE_LIMIT)
async def delete_auth_client(
    request: Request,
    org_id: str,
    client_pk: str,
    db: Session = Depends(get_db_session),
    _gate: object = Depends(require_feature(FeatureName.API_CLIENTS)),
):
    """Hard-delete. Only allowed when ``disabled=true``.

    The disable-first rail prevents an admin from accidentally
    deleting an in-use client. The pattern is "disable -> verify
    nothing breaks for a window -> delete"; without the rail, a
    fat-fingered click could drop a production integration in one
    request.
    """
    user = await _require_org_admin_for(request, org_id)
    _get_org_or_404(db, org_id)
    row = _get_client_or_404(db, org_id, client_pk)

    if not row.disabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Disable the client before deleting it.",
        )

    client_id_for_audit = row.client_id
    org_for_audit = str(row.organization_id)
    row.soft_delete()
    db.commit()

    auth_client_audit_log(
        AuthClientLifecycleEvent.DELETED,
        org_id=org_for_audit,
        client_id=client_id_for_audit,
        actor_id=str(user.id),
        ip=_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return None
