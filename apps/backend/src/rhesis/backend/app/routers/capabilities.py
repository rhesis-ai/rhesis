"""Capabilities and permissions endpoints.

``GET /capabilities``
    Returns the full catalog of platform capabilities (report-only in Phase 1;
    backed by the ``permission`` DB table in Phase 2).

``GET /me/permissions``
    Returns the caller's effective permission set for a given project (or
    org-scoped when ``project_id`` is omitted).  The list is computed by
    running every known capability through :func:`~rhesis.backend.app.auth.rbac.authorize`,
    so it automatically reflects the active authorization provider (community
    in Phase 1, EE in Phase 2).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import get_all_capabilities
from rhesis.backend.app.auth.principal import resolve_principal
from rhesis.backend.app.auth.rbac import authorize
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_db_session

router = APIRouter(tags=["capabilities"])


@router.get("/capabilities", response_model=list[str])
def list_capabilities(
    current_user=Depends(require_current_user_or_token),
) -> list[str]:
    """Return the catalog of all platform capabilities.

    Phase 1: returns the static community list.
    Phase 2 (SP7): reads from the live ``permission`` DB table.

    Authentication is required; the list itself is not filtered by caller —
    it reflects what *exists*, not what the caller *holds*.  Use
    ``GET /me/permissions`` to get the caller's effective subset.
    """
    return get_all_capabilities()


@router.get("/me/permissions", response_model=list[str])
def get_my_permissions(
    project_id: Optional[UUID] = Query(
        None,
        description=(
            "Evaluate permissions in the context of this project. "
            "Omit for org-scoped permissions only."
        ),
    ),
    db: Session = Depends(get_tenant_db_session),
    current_user=Depends(require_current_user_or_token),
) -> list[str]:
    """Return the caller's effective permissions for a given project (or org-scoped).

    Evaluates every known capability through :func:`authorize` so the returned
    list accurately reflects the active authorization provider.

    Args:
        project_id: Optional project scope.  When present, project-scoped
            capabilities are included if the caller is an org owner or a member
            of that project.  When absent, only org-scoped capabilities the
            caller holds are returned.

    Returns:
        Sorted list of ``"resource:action"`` strings.
    """
    principal = resolve_principal(current_user)
    return [
        cap
        for cap in get_all_capabilities()
        if authorize(principal, cap, project_id=project_id, db=db)
    ]
