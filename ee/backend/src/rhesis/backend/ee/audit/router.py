"""Audit log read API.

- ``GET /audit-events``           -- list, with the usual ``$filter``/``$select``/
  ``skip``/``limit``/``sort_by`` and an optional keyset ``cursor``
- ``GET /audit-events/actions``   -- every action the log can hold
- ``GET /audit-events/{event_id}`` -- one event

Gated on ``FeatureName.AUDIT_LOG`` (404 when unavailable) and ``audit_log:read``.
Nothing here writes: the table is append-only.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission, capability, get_all_capabilities
from rhesis.backend.app.auth.feature_gates import require_feature
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.features import FeatureName
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.odata import apply_select
from rhesis.backend.ee.audit import crud as audit_crud
from rhesis.backend.ee.audit.models import AuditEvent
from rhesis.backend.ee.audit.schemas import AuditActionRead, AuditEventRead
from rhesis.backend.events.audit_actions import known_actions

router = APIRouter(
    prefix="/audit-events",
    tags=["audit-log"],
    dependencies=[Depends(require_feature(FeatureName.AUDIT_LOG))],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=list[AuditEventRead], **capability(Permission.AuditLog.READ))
@with_count_header(model=AuditEvent)
def list_audit_events(
    response: Response,
    skip: int = 0,
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = audit_crud.CURSOR_SORT_FIELD,
    sort_order: str = "desc",
    filter: Optional[str] = Query(None, alias="$filter", description="OData filter expression"),
    select: Optional[str] = Query(
        None, alias="$select", description="Comma-separated list of fields to return"
    ),
    cursor: Optional[UUID] = Query(
        None,
        description=(
            "Id of the last event already read. Continues after it on (occurred_at, id) "
            "in sort_order; only with sort_by=occurred_at."
        ),
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """List the organization's audit events, newest first by default."""
    organization_id, _ = tenant_context
    after = None
    if cursor is not None:
        if sort_by != audit_crud.CURSOR_SORT_FIELD:
            raise HTTPException(status_code=400, detail="cursor needs sort_by=occurred_at")
        after = audit_crud.get_audit_event(db, cursor, organization_id)
        if after is None:
            raise HTTPException(status_code=400, detail="Unknown cursor")

    rows = audit_crud.list_audit_events(
        db,
        organization_id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        after=after,
    )
    events = [AuditEventRead.model_validate(row) for row in rows]
    if select:
        serialized = [event.model_dump(mode="json") for event in events]
        return JSONResponse(content=apply_select(serialized, select))
    return events


@router.get(
    "/actions", response_model=list[AuditActionRead], **capability(Permission.AuditLog.READ)
)
def list_audit_actions():
    """Every action the log can hold: derived from the capability catalog, plus audit-only ones."""
    result = []
    for action in sorted(known_actions(get_all_capabilities())):
        resource, _, verb = action.partition(".")
        result.append(AuditActionRead(action=action, resource=resource, verb=verb))
    return result


@router.get("/{event_id}", response_model=AuditEventRead, **capability(Permission.AuditLog.READ))
def read_audit_event(
    event_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """One audit event.

    ``content_changes`` is not returned: decrypting it waits on the org's
    "include content" setting (PR 9), which does not exist yet.
    """
    organization_id, _ = tenant_context
    event = audit_crud.get_audit_event(db, event_id, organization_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return event
