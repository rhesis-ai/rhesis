"""Local-mode Rhesis platform API key management.

All endpoints are gated by :func:`require_local_mode` (they 404 on non-local
deployments, preventing enumeration) and by ``require_current_user_or_token``.
The organization is always resolved from the authenticated user, so a caller
can only read or write their own organization's platform key. The raw key is
never returned by any response.

PUT/DELETE additionally require ``Permission.Platform.MANAGE`` (owner-only,
even on a community deployment with no EE role provider -- see the PDP's
org-owner fallback) via the ``apply_authz_backstop`` PEP, since they mutate a
credential shared by the whole organization. GET is read-only and exposes no
more than a masked key suffix, so it stays open to any authenticated member.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.feature_gates import require_local_mode
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.platform import PlatformKeyStatus, PlatformKeyUpdate
from rhesis.backend.app.services import platform_key as platform_key_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/platform",
    tags=["platform"],
    dependencies=[Depends(require_local_mode)],
    responses={404: {"description": "Not found"}},
    # Local-only endpoints: keep them out of the OpenAPI schema so they are not
    # enumerable on non-local (SaaS) deployments. require_local_mode still
    # enforces the 404 behavior regardless.
    include_in_schema=False,
)


@router.get("/rhesis-key", response_model=PlatformKeyStatus)
def read_rhesis_key_status(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_current_user_or_token),
) -> PlatformKeyStatus:
    """Return the org platform key status (never the raw key).

    Uses ``refresh=True`` for an on-demand, TTL-bounded re-probe: the status
    page gets fresh data, but repeated loads within the cache window still read
    the cached result rather than re-hitting the network.
    """
    status = platform_key_service.get_platform_key_status(
        db, current_user.organization_id, refresh=True
    )
    return PlatformKeyStatus(**status)


@router.put(
    "/rhesis-key", response_model=PlatformKeyStatus, **capability(Permission.Platform.MANAGE)
)
def set_rhesis_key(
    payload: PlatformKeyUpdate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_current_user_or_token),
) -> PlatformKeyStatus:
    """Store the org platform key (encrypted) and return its validated status."""
    try:
        status = platform_key_service.set_platform_api_key(
            db, current_user.organization_id, payload.key
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return PlatformKeyStatus(**status)


@router.delete(
    "/rhesis-key", response_model=PlatformKeyStatus, **capability(Permission.Platform.MANAGE)
)
def delete_rhesis_key(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_current_user_or_token),
) -> PlatformKeyStatus:
    """Clear the org's stored platform key and return the resulting status.

    Clearing the DB-stored key does not guarantee ``configured=False``: a
    process-wide ``RHESIS_API_KEY`` env var, if set, remains the effective
    key. Returning the real status (instead of a hardcoded dict) keeps this
    consistent with ``set_rhesis_key`` and reflects that fallback correctly.
    """
    status = platform_key_service.clear_platform_api_key(db, current_user.organization_id)
    return PlatformKeyStatus(**status)
