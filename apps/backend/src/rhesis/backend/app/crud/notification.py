"""CRUD operations for in-app notifications.

Every query here adds an explicit ``Notification.user_id == user_id`` filter.
The ambient auto-filter (see "Ambient Request Scope" in apps/backend/AGENTS.md)
scopes by organization and project automatically, but not by user -- without
this filter, one user's `GET /notifications/summary` would return every
recipient's rows in the same org/project.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from rhesis.backend.app.models.notification import Notification


def create_notification(
    db: Session,
    *,
    event_type: str,
    section: str,
    title: str,
    user_id: str,
    body: Optional[str] = None,
    is_failure: bool = False,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    payload: Optional[Dict[str, Any]] = None,
    organization_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Notification:
    """Create and commit a notification for its recipient."""
    notification = Notification(
        event_type=event_type,
        section=section,
        title=title,
        body=body,
        is_failure=is_failure,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        user_id=user_id,
        organization_id=organization_id,
        project_id=project_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


#: Cap on unread rows scanned for highlight ids per /summary call. Counts are
#: aggregated in SQL and stay exact regardless; only the highlight list is
#: bounded. A grid page shows at most ~50 rows, so this is far more than the UI
#: can use, and it keeps the endpoint's cost flat for a user who lets
#: notifications pile up instead of growing with every completed job.
_SUMMARY_HIGHLIGHT_SCAN_LIMIT = 200


def get_notification_summary(db: Session, user_id: str) -> Dict[str, Dict[str, Any]]:
    """Unread count and highlightable entity ids, grouped by section.

    Sections with zero unread notifications are omitted -- the frontend
    treats an absent key the same as ``{"unread": 0, "entity_ids": []}``.
    """
    counts = (
        db.query(Notification.section, func.count(Notification.id))
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .group_by(Notification.section)
        .all()
    )
    summary: Dict[str, Dict[str, Any]] = {
        section: {"unread": count, "entity_ids": []} for section, count in counts
    }
    if not summary:
        return summary

    recent = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .order_by(Notification.created_at.desc())
        .limit(_SUMMARY_HIGHLIGHT_SCAN_LIMIT)
        .all()
    )
    for row in recent:
        bucket = summary.get(row.section)
        if bucket is None:
            continue
        if row.entity_id is not None:
            bucket["entity_ids"].append(row.entity_id)
        extra_ids = (row.payload or {}).get("entity_ids")
        if extra_ids:
            bucket["entity_ids"].extend(extra_ids)
    return summary


def get_notifications(
    db: Session,
    user_id: str,
    section: Optional[str] = None,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> List[Notification]:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if section:
        query = query.filter(Notification.section == section)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()


def mark_notifications_read(
    db: Session,
    user_id: str,
    section: Optional[str] = None,
    ids: Optional[List[UUID]] = None,
) -> int:
    """Stamp ``read_at`` on the caller's unread notifications matching the filters.

    ``section`` and ``ids`` narrow together (AND), so passing both means "these
    ids, within this section" and can never mark more than either filter alone
    would. Returns 0 when neither is given rather than marking everything read
    -- the router rejects that case with a 400, this is the belt-and-braces
    half of the same guard.
    """
    if not section and not ids:
        return 0

    query = db.query(Notification).filter(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    if section:
        query = query.filter(Notification.section == section)
    if ids:
        query = query.filter(Notification.id.in_(ids))

    count = query.update({Notification.read_at: func.now()}, synchronize_session=False)
    db.commit()
    return count
