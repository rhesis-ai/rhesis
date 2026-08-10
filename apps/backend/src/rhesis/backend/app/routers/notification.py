"""In-app notification endpoints: badge summary, list, mark-as-read.

Notifications are created only by the system (via
``services.notification.notify``, called from Celery task hooks and, in a
follow-up plan, websocket handlers) -- this router is read/update only, no
create/delete.
"""

from typing import List, Optional

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from rhesis.backend.app import schemas
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.crud.notification import (
    get_notification_summary,
    get_notifications,
    mark_notifications_read,
)
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.routers.base import RhesisRouter

router = RhesisRouter(
    prefix="/notifications",
    tags=["notification"],
    dependencies=[Depends(require_current_user_or_token)],
    resource="notification",
)


@router.get(
    "/summary",
    response_model=schemas.NotificationSummaryResponse,
    **capability(Permission.Notification.READ),
)
def read_notification_summary(
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
) -> schemas.NotificationSummaryResponse:
    """Unread count and highlightable entity ids per sidebar section.

    Called on mount and on every active-project switch -- the ambient
    auto-filter already scopes this to the caller's org and active project.
    """
    _organization_id, user_id = tenant_context
    summary = get_notification_summary(db, user_id=user_id)
    return schemas.NotificationSummaryResponse(sections=summary)


@router.get(
    "/",
    response_model=List[schemas.NotificationRead],
    **capability(Permission.Notification.READ),
)
def read_notifications(
    section: Optional[str] = None,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = Query(100, le=200),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
) -> List[schemas.NotificationRead]:
    """Paginated notification history. Not consumed by the sidebar badge --
    that's /summary -- this is for a future notification drawer."""
    _organization_id, user_id = tenant_context
    return get_notifications(
        db,
        user_id=user_id,
        section=section,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/read",
    # Gated on READ, not a separate :update -- see Permission.Notification.
    **capability(Permission.Notification.READ),
)
def mark_read(
    body: schemas.NotificationMarkReadRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
) -> dict:
    """Mark notifications read. At least one of ``section``/``ids`` required."""
    if not body.section and not body.ids:
        raise HTTPException(status_code=400, detail="section or ids is required")
    _organization_id, user_id = tenant_context
    updated = mark_notifications_read(db, user_id=user_id, section=body.section, ids=body.ids)
    return {"updated": updated}
