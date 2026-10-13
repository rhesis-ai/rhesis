"""Reads and writes of ``audit_destination``, and the reads delivery makes of ``audit_event``."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import or_, select, tuple_
from sqlalchemy.orm import Session

from rhesis.backend.ee.audit.models import AuditEvent
from rhesis.backend.ee.audit.streaming.models import AuditDestination

# Rows recorded before this are committed or never will be. Read in its own statement, before
# the events are, so a transaction that commits in between is already visible to that read.
# - The oldest open writing transaction's start: its audit rows are not visible yet, and every
#   one of them has a later recorded_at. pg_stat_activity shows the xact_start of sessions of
#   the same database role only; the app and workers share one.
# - The lag covers the instant between an insert stamping recorded_at and its transaction
#   getting an id, and writers under other roles.
_SAFE_BOUND = sa.text(
    """
    SELECT LEAST(
        clock_timestamp() - make_interval(secs => CAST(:lag AS double precision)),
        (SELECT min(xact_start) FROM pg_stat_activity
         WHERE datname = current_database()
           AND pid <> pg_backend_pid()
           AND backend_xid IS NOT NULL)
    )
    """
)


def list_destinations(db: Session) -> list[AuditDestination]:
    return list(db.scalars(select(AuditDestination).order_by(AuditDestination.created_at)))


def get_destination(db: Session, destination_id: UUID) -> Optional[AuditDestination]:
    return db.scalars(select(AuditDestination).where(AuditDestination.id == destination_id)).first()


def transaction_start(db: Session) -> datetime:
    return db.execute(select(sa.func.now())).scalar_one()


def create_destination(db: Session, destination: AuditDestination) -> AuditDestination:
    db.add(destination)
    db.flush()
    db.refresh(destination)
    return destination


def delete_destination(db: Session, destination: AuditDestination) -> None:
    db.delete(destination)
    db.flush()


def _due() -> tuple:
    """Running, and not waiting out a backoff."""
    return (
        AuditDestination.paused.is_(False),
        or_(
            AuditDestination.next_attempt_at.is_(None),
            # The current time: now() is when the transaction started.
            AuditDestination.next_attempt_at <= sa.func.clock_timestamp(),
        ),
    )


def due_destination_ids(db: Session) -> list[UUID]:
    return list(db.scalars(select(AuditDestination.id).where(*_due())))


def lock_due_destination(db: Session, destination_id: UUID) -> Optional[AuditDestination]:
    """The destination, locked for this transaction, if it is still due and no one else holds it."""
    return db.scalars(
        select(AuditDestination)
        .where(AuditDestination.id == destination_id, *_due())
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    ).first()


def safe_bound(db: Session, lag_seconds: float) -> datetime:
    # pg_stat_activity is cached for the rest of a transaction once read; read it fresh.
    db.execute(sa.text("SELECT pg_stat_clear_snapshot()"))
    return db.execute(_SAFE_BOUND, {"lag": lag_seconds}).scalar_one()


def events_after(
    db: Session,
    organization_id: UUID,
    cursor: tuple[datetime, UUID],
    before: datetime,
    limit: int,
) -> list[AuditEvent]:
    """The org's next events after ``cursor`` on ``(recorded_at, id)``, recorded before ``before``.

    No index covers this yet: the BRIN on ``recorded_at`` narrows it, and the
    rows after a cursor are few. Add ``(organization_id, recorded_at, id)`` if
    measurements say so.
    """
    key = tuple_(AuditEvent.recorded_at, AuditEvent.id)
    return list(
        db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.organization_id == organization_id,
                key > tuple_(*cursor),
                AuditEvent.recorded_at < before,
            )
            .order_by(AuditEvent.recorded_at, AuditEvent.id)
            .limit(limit)
        )
    )
