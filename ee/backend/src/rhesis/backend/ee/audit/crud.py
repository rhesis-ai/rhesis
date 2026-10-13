"""Reads and writes of ``audit_event``, the append-only store from migration ``ef7fe15a29ee``.

Writes are Core, not ORM: the table has no ``nano_id``/``updated_at``/``deleted_at`` for
``Base`` to map, and a Core insert on the session's connection triggers no session
events, so writing an audit row never captures itself. Reads use the read-only
``AuditEvent`` model. Nothing here updates or deletes.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import tuple_
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from rhesis.backend.app.utils.encryption import EncryptedString
from rhesis.backend.app.utils.query_utils import QueryBuilder
from rhesis.backend.ee.audit.models import AuditEvent

audit_event = sa.table(
    "audit_event",
    sa.column("organization_id", PG_UUID(as_uuid=True)),
    sa.column("project_id", PG_UUID(as_uuid=True)),
    sa.column("occurred_at", sa.DateTime(timezone=True)),
    sa.column("action", sa.Text),
    sa.column("outcome", sa.Text),
    sa.column("status_code", sa.Integer),
    sa.column("actor_type", sa.Text),
    sa.column("actor_id", PG_UUID(as_uuid=True)),
    sa.column("actor_credential_id", sa.Text),
    sa.column("actor_credential_hint", sa.Text),
    sa.column("actor_label", sa.Text),
    sa.column("channel", sa.Text),
    sa.column("ip", INET),
    sa.column("user_agent", sa.Text),
    sa.column("resource_id", PG_UUID(as_uuid=True)),
    sa.column("resource_label", sa.Text),
    sa.column("request_id", sa.Text),
    sa.column("trace_id", sa.Text),
    sa.column("span_id", sa.Text),
    sa.column("job_id", PG_UUID(as_uuid=True)),
    sa.column("changes", JSONB),
    sa.column("content_changes", EncryptedString()),
)

_CURRENT_ORG = sa.text("SELECT current_setting('app.current_organization', true)")
_SET_ORG = sa.text("SELECT set_config('app.current_organization', :org, true)")


def insert_audit_event(conn: Connection, row: dict, *, as_org: bool) -> None:
    """Insert one row. ``as_org`` points the RLS setting at the row's org for
    the insert, for a change made outside that org's context (a new org)."""
    if not as_org:
        conn.execute(sa.insert(audit_event).values(row))
        return
    previous = conn.execute(_CURRENT_ORG).scalar()
    conn.execute(_SET_ORG, {"org": str(row["organization_id"])})
    # No finally: after a failed insert the transaction is aborted and rolls back anyway.
    conn.execute(sa.insert(audit_event).values(row))
    conn.execute(_SET_ORG, {"org": previous or ""})


DEFAULT_SORT_FIELD = "occurred_at"
# The one order a safe upper bound exists for, so the only one the cursor walks.
CURSOR_SORT_FIELD = "recorded_at"
SAFE_LAG_SECONDS = 5.0

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


def safe_bound(db: Session, lag_seconds: float) -> datetime:
    """No row recorded before this can still appear: read ``recorded_at`` up to it."""
    # pg_stat_activity is cached for the rest of a transaction once read; read it fresh.
    db.execute(sa.text("SELECT pg_stat_clear_snapshot()"))
    return db.execute(_SAFE_BOUND, {"lag": lag_seconds}).scalar_one()


def get_audit_event(db: Session, event_id: UUID, organization_id: str) -> Optional[AuditEvent]:
    return (
        QueryBuilder(db, AuditEvent)
        .with_organization_filter(organization_id)
        .query.filter(AuditEvent.id == event_id)
        .first()
    )


def _keyset_after(builder: QueryBuilder, column, key: tuple, sort_order: str) -> QueryBuilder:
    """Rows past ``key``, a ``(column, id)`` pair, in ``sort_order``."""
    pair, bound = tuple_(column, AuditEvent.id), tuple_(*key)
    if sort_order.lower() == "desc":
        past = (pair < bound, column <= key[0])
    else:
        past = (pair > bound, column >= key[0])
    # The plain comparison is redundant, but a BRIN index can use it and not the row one.
    return builder.with_custom_filter(lambda q: q.filter(*past))


def list_audit_events(
    db: Session,
    organization_id: str,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = DEFAULT_SORT_FIELD,
    sort_order: str = "desc",
    filter: Optional[str] = None,
    after: Optional[AuditEvent] = None,
) -> List[AuditEvent]:
    """A page of events. ``after`` continues a keyset walk on ``(recorded_at, id)``.

    ``id`` breaks ties in the sort direction, so a keyset page and an offset page
    order rows the same way. Ascending on ``recorded_at``, the order a tail reads
    in, stops at the safe bound, so a row that commits late never lands behind a
    page already read.
    """
    builder = (
        QueryBuilder(db, AuditEvent)
        .with_organization_filter(organization_id)
        .with_odata_filter(filter)
    )
    if after is not None:
        key = (after.recorded_at, after.id)
        builder = _keyset_after(builder, AuditEvent.recorded_at, key, sort_order)
    if sort_by == CURSOR_SORT_FIELD and sort_order.lower() == "asc":
        bound = safe_bound(db, SAFE_LAG_SECONDS)
        builder = builder.with_custom_filter(lambda q: q.filter(AuditEvent.recorded_at < bound))
    return (
        builder.with_sorting(
            sort_by, sort_order, secondary_sort_by="id", secondary_sort_order=sort_order
        )
        .with_pagination(skip, limit)
        .all()
    )


def _export_query(
    db: Session, organization_id: str, filter: Optional[str], until: datetime
) -> QueryBuilder:
    return (
        QueryBuilder(db, AuditEvent)
        .with_organization_filter(organization_id)
        .with_odata_filter(filter)
        .with_custom_filter(lambda q: q.filter(AuditEvent.occurred_at <= until))
    )


def count_export_events(
    db: Session, organization_id: str, filter: Optional[str], until: datetime
) -> int:
    return _export_query(db, organization_id, filter, until).count()


def export_page(
    db: Session,
    organization_id: str,
    *,
    filter: Optional[str],
    sort_order: str,
    until: datetime,
    after: Optional[tuple],
    limit: int,
) -> List[AuditEvent]:
    """Up to ``limit`` events that happened by ``until``, after the ``(occurred_at, id)``
    key ``after``. Not capped at a page of 100 like the list."""
    builder = _export_query(db, organization_id, filter, until)
    if after is not None:
        builder = _keyset_after(builder, AuditEvent.occurred_at, after, sort_order)
    builder = builder.with_sorting(
        DEFAULT_SORT_FIELD, sort_order, secondary_sort_by="id", secondary_sort_order=sort_order
    )
    return builder.build().limit(limit).all()
