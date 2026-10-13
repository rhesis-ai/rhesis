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


CURSOR_SORT_FIELD = "occurred_at"


def get_audit_event(db: Session, event_id: UUID, organization_id: str) -> Optional[AuditEvent]:
    return (
        QueryBuilder(db, AuditEvent)
        .with_organization_filter(organization_id)
        .query.filter(AuditEvent.id == event_id)
        .first()
    )


def _keyset_after(builder: QueryBuilder, key: tuple, sort_order: str) -> QueryBuilder:
    """Rows past ``key``, an ``(occurred_at, id)`` pair, in ``sort_order``."""
    column = tuple_(AuditEvent.occurred_at, AuditEvent.id)
    bound = tuple_(*key)
    past = column < bound if sort_order.lower() == "desc" else column > bound
    return builder.with_custom_filter(lambda q: q.filter(past))


def list_audit_events(
    db: Session,
    organization_id: str,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = CURSOR_SORT_FIELD,
    sort_order: str = "desc",
    filter: Optional[str] = None,
    after: Optional[AuditEvent] = None,
) -> List[AuditEvent]:
    """A page of events. ``after`` continues a keyset walk on ``(occurred_at, id)``.

    ``id`` breaks ties in the same direction as ``occurred_at``, so a keyset
    page and an offset page order rows the same way.
    """
    builder = (
        QueryBuilder(db, AuditEvent)
        .with_organization_filter(organization_id)
        .with_odata_filter(filter)
    )
    if after is not None:
        builder = _keyset_after(builder, (after.occurred_at, after.id), sort_order)
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
        builder = _keyset_after(builder, after, sort_order)
    builder = builder.with_sorting(
        CURSOR_SORT_FIELD, sort_order, secondary_sort_by="id", secondary_sort_order=sort_order
    )
    return builder.build().limit(limit).all()
