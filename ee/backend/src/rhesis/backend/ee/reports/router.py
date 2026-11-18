"""``GET /reports/{report_id}/audit-trail``: the report's own audit entries.

Live, not a frozen section: the entries are written at publish and after it (exports).
Gated on ``FeatureName.AUDIT_LOG`` and ``report:read``. It shows only this report's
``report.*`` entries; the full audit log stays behind ``audit_log:read``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.feature_gates import require_feature
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.features import FeatureName
from rhesis.backend.app.services.report.service import ReportError, load_report
from rhesis.backend.ee.audit import crud as audit_crud

TRAIL_LIMIT = 100

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[
        Depends(require_feature(FeatureName.AUDIT_LOG)),
        Depends(require_current_user_or_token),
    ],
    responses={404: {"description": "Not found"}},
)


class ReportAuditEntry(BaseModel):
    id: uuid.UUID
    action: str
    actor_label: Optional[str] = None
    occurred_at: datetime


@router.get(
    "/{report_id}/audit-trail",
    response_model=List[ReportAuditEntry],
    **capability(Permission.Report.READ),
)
def read_report_audit_trail(
    report_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    organization_id, user_id = tenant_context
    try:
        load_report(db, report_id, organization_id, user_id)
    except ReportError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    events = audit_crud.list_audit_events(
        db,
        organization_id,
        limit=TRAIL_LIMIT,
        sort_order="desc",
        filter=f"resource_id eq {report_id} and startswith(action,'report.')",
    )
    return [ReportAuditEntry.model_validate(e, from_attributes=True) for e in events]
