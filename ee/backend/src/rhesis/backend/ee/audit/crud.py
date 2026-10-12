"""Writes to ``audit_event``, the append-only store from migration ``ef7fe15a29ee``.

Core, not ORM: the table has no ``nano_id``/``updated_at``/``deleted_at`` for
``Base`` to map, and a Core insert on the session's connection triggers no
session events, so writing an audit row never captures itself.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.engine import Connection

audit_event = sa.table(
    "audit_event",
    sa.column("organization_id", UUID(as_uuid=True)),
    sa.column("project_id", UUID(as_uuid=True)),
    sa.column("occurred_at", sa.DateTime(timezone=True)),
    sa.column("action", sa.Text),
    sa.column("outcome", sa.Text),
    sa.column("status_code", sa.Integer),
    sa.column("actor_type", sa.Text),
    sa.column("actor_id", UUID(as_uuid=True)),
    sa.column("actor_credential_id", sa.Text),
    sa.column("actor_credential_hint", sa.Text),
    sa.column("actor_label", sa.Text),
    sa.column("channel", sa.Text),
    sa.column("ip", INET),
    sa.column("user_agent", sa.Text),
    sa.column("resource_id", UUID(as_uuid=True)),
    sa.column("resource_label", sa.Text),
    sa.column("request_id", sa.Text),
    sa.column("trace_id", sa.Text),
    sa.column("span_id", sa.Text),
    sa.column("job_id", UUID(as_uuid=True)),
    sa.column("changes", JSONB),
    sa.column("content_changes", sa.Text),
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
