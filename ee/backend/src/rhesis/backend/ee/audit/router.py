"""Audit log read API.

- ``GET /audit-events``           -- list, with the usual ``$filter``/``$select``/
  ``skip``/``limit``/``sort_by`` and an optional keyset ``cursor``
- ``GET /audit-events/actions``   -- every action the log can hold
- ``GET /audit-events/{event_id}`` -- one event
- ``GET``/``PATCH /audit-events/settings`` -- retention and privacy; reading needs
  ``audit_log:read`` (so an Auditor sees them), changing needs ``audit_log:manage``
- ``POST /audit-events/exports`` -- export as JSONL or CSV, as a job (``audit_log:export``)
- ``GET /audit-events/exports/{job_id}/download`` -- the finished file (``audit_log:export``)

Gated on ``FeatureName.AUDIT_LOG`` (404 when unavailable) and ``audit_log:read``.
Detail returns stored content only while the org includes content (see ``settings``).
Listing and reading an event record ``audit_log.viewed`` (see ``self_audit``);
``/actions`` does not, as it returns only action names, never an event.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission, capability, get_all_capabilities
from rhesis.backend.app.auth.feature_gates import require_feature
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.features import FeatureName
from rhesis.backend.app.services.storage_service import NotSupportedError, StorageService
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.odata import apply_select
from rhesis.backend.ee.audit import crud as audit_crud
from rhesis.backend.ee.audit import settings as audit_settings
from rhesis.backend.ee.audit.export import service as audit_export
from rhesis.backend.ee.audit.models import AuditEvent
from rhesis.backend.ee.audit.schemas import (
    AuditActionRead,
    AuditEventDetail,
    AuditEventRead,
    AuditExportCreate,
    AuditExportCreated,
    AuditLogSettingsRead,
    AuditLogSettingsUpdate,
)
from rhesis.backend.ee.audit.self_audit import record_view
from rhesis.backend.events.audit_actions import known_actions

FILE_GONE = "Export file no longer exists"

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
    record_view(db, organization_id)
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


@router.get(
    "/settings", response_model=AuditLogSettingsRead, **capability(Permission.AuditLog.READ)
)
def read_audit_log_settings(
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """Retention and privacy settings, with defaults for anything never set."""
    organization_id, _ = tenant_context
    return audit_settings.read_settings(audit_settings.organization(db, organization_id))


@router.patch(
    "/settings", response_model=AuditLogSettingsRead, **capability(Permission.AuditLog.MANAGE)
)
def update_audit_log_settings(
    update: AuditLogSettingsUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """Change the fields sent. Recorded in the log itself as ``organization.updated``."""
    organization_id, _ = tenant_context
    org = audit_settings.organization(db, organization_id)
    try:
        return audit_settings.update_settings(db, org, update)
    except audit_settings.RetentionAboveCap as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post(
    "/exports",
    response_model=AuditExportCreated,
    status_code=202,
    **capability(Permission.AuditLog.EXPORT),
)
def create_audit_export(
    request: AuditExportCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user=Depends(require_current_user_or_token),
):
    """Export the events matching ``filter`` as JSONL or CSV, as a background job.

    Recorded as ``audit_log.exported``. Poll ``GET /jobs/{task_id}``, or wait for
    the notification; then download from ``/audit-events/exports/{job_id}/download``.
    """
    return audit_export.start_export(db, current_user, request)


@router.get("/exports/{job_id}/download", **capability(Permission.AuditLog.EXPORT))
def download_audit_export(
    job_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """A finished export: a redirect to a short-lived link, or the file itself on
    local storage. Each download is recorded as a read of the log."""
    organization_id, user_id = tenant_context
    try:
        export = audit_export.finished_export(db, job_id, organization_id, user_id)
    except audit_export.ExportNotFound as e:
        raise HTTPException(status_code=404, detail="Export not found") from e
    except audit_export.ExportNotReady as e:
        raise HTTPException(status_code=409, detail=f"Export is {e}, not completed") from e
    except audit_export.ExportGone as e:
        raise HTTPException(status_code=404, detail=FILE_GONE) from e

    storage = StorageService()
    disposition = f'attachment; filename="{export.filename}"'
    try:
        url = storage.presigned_url(
            export.path, expires_in=audit_export.LINK_SECONDS, response_disposition=disposition
        )
    except NotSupportedError:
        url = None
    if url is None and not storage.object_exists(export.path):
        raise HTTPException(status_code=404, detail=FILE_GONE)
    audit_export.record_download(db, organization_id, job_id, export)
    if url is not None:
        return RedirectResponse(url=url, status_code=302)
    return StreamingResponse(
        storage.iter_object(export.path),
        media_type=export.content_type,
        headers={"Content-Disposition": disposition},
    )


@router.get("/{event_id}", response_model=AuditEventDetail, **capability(Permission.AuditLog.READ))
def read_audit_event(
    event_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """One audit event, with ``content_changes`` decrypted while the org includes content."""
    organization_id, _ = tenant_context
    event = audit_crud.get_audit_event(db, event_id, organization_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Audit event not found")
    detail = audit_settings.event_detail(event, audit_settings.organization(db, organization_id))
    record_view(db, organization_id)
    return detail
