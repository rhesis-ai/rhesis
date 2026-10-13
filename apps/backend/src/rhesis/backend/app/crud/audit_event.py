"""Retention reads and the purge of ``audit_event`` (migration ``ef7fe15a29ee``).

Core because the purge job is core; the EE read API has its own module. Both
statements rely on RLS, so the session must be scoped to the org.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def has_audit_events_before(db: Session, organization_id: UUID, before: datetime) -> bool:
    return db.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM audit_event "
            "WHERE organization_id = CAST(:org AS uuid) AND recorded_at < :before)"
        ),
        {"org": str(organization_id), "before": before},
    ).scalar_one()


def purge_audit_events(
    db: Session,
    organization_id: UUID,
    before: datetime,
    trace_id: str,
    span_id: str,
    job_id: Optional[UUID] = None,
) -> int:
    """Delete the org's rows recorded before ``before``; returns the count.

    ``audit_event_purge`` is the only delete path, and it writes its own
    ``audit_log.purged`` row.
    """
    return db.execute(
        text(
            "SELECT audit_event_purge(CAST(:org AS uuid), :before, :trace_id, :span_id, "
            "CAST(:job_id AS uuid))"
        ),
        {
            "org": str(organization_id),
            "before": before,
            "trace_id": trace_id,
            "span_id": span_id,
            "job_id": str(job_id) if job_id else None,
        },
    ).scalar_one()
