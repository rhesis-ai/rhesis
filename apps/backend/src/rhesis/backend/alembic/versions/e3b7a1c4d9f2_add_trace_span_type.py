"""Add trace.span_type

Every span gets one type, by Langfuse's rule: ai.operation.type if set, else
llm.invoke if the span names a model (ai.model.name), else span. The Python
version of the rule is app/services/telemetry/span_types.py; ingest uses that
one and this migration backfills with the SQL below. Change both together --
tests/backend/alembic/test_trace_span_type_migration.py runs them against the
same cases.

The column is added NOT NULL DEFAULT 'span', which Postgres 11+ records as
metadata without rewriting the table, and every untyped span is already right.
The backfill then walks the table in primary-key batches and only writes rows
whose type differs, so it is linear, and safe to re-run. A last sweep catches
rows the old code inserted while the batches ran.

trace has FORCE ROW LEVEL SECURITY, so a plain UPDATE under a role without
BYPASSRLS matches nothing. With BYPASSRLS (prod's rhesis-admin), each batch
commits on its own inside an autocommit block: no long transaction, no table
lock. Without it (self-hosted), the batches run in the migration's transaction
with RLS disabled; the ALTER TABLE holds an ACCESS EXCLUSIVE lock until commit,
so no other session ever sees RLS off.

The (project_id, span_type, start_time DESC) index serves "spans of this type in
this project, newest first", and builds CONCURRENTLY.

Revision ID: e3b7a1c4d9f2
Revises: 2dfc229bb2a8
Create Date: 2026-09-29
"""

from contextlib import contextmanager
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.idempotency import column_exists

revision: str = "e3b7a1c4d9f2"
down_revision: Union[str, None] = "2dfc229bb2a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "idx_trace_project_span_type_time"
_BATCH_SIZE = 10_000
_LOCK_TIMEOUT = "120s"

# Mirrors classify_span_type -- migrations can't import app code. Only a non-empty
# JSON string counts as set; 64 is SpanType.MAX_LENGTH.
_SPAN_TYPE_SQL = """
    CASE
        WHEN jsonb_typeof(attributes -> 'ai.operation.type') = 'string'
             AND attributes ->> 'ai.operation.type' <> ''
            THEN left(attributes ->> 'ai.operation.type', 64)
        WHEN jsonb_typeof(attributes -> 'ai.model.name') = 'string'
             AND attributes ->> 'ai.model.name' <> ''
            THEN 'llm.invoke'
        ELSE 'span'
    END
"""


def _has_bypassrls(conn) -> bool:
    return bool(
        conn.execute(
            sa.text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    )


def _update_range(conn, lower, upper) -> int:
    bounds = []
    if lower is not None:
        bounds.append("id > CAST(:lower AS uuid)")
    if upper is not None:
        bounds.append("id <= CAST(:upper AS uuid)")
    bounds.append(f"span_type IS DISTINCT FROM ({_SPAN_TYPE_SQL})")
    result = conn.execute(
        sa.text(f"UPDATE trace SET span_type = {_SPAN_TYPE_SQL} WHERE {' AND '.join(bounds)}"),
        {"lower": lower, "upper": upper},
    )
    return result.rowcount


def _backfill(conn, batch_size: int = _BATCH_SIZE) -> int:
    """Set span_type on every row, batch_size ids at a time. Returns rows changed."""
    changed = 0
    lower = None
    while True:
        after = "" if lower is None else "WHERE id > CAST(:lower AS uuid)"
        # Last id of the next batch; None means what's left is the final batch.
        upper = conn.execute(
            sa.text(f"SELECT id FROM trace {after} ORDER BY id OFFSET :skip LIMIT 1"),
            {"lower": lower, "skip": batch_size - 1},
        ).scalar()
        changed += _update_range(conn, lower, upper)
        if upper is None:
            break
        lower = str(upper)
    # Rows inserted behind the cursor while the batches ran.
    return changed + _update_range(conn, None, None)


def _add_column(conn) -> None:
    if not column_exists(conn, "trace", "span_type"):
        op.add_column(
            "trace",
            sa.Column("span_type", sa.String(64), nullable=False, server_default="span"),
        )


def _backfill_under_rls(conn) -> None:
    enabled = conn.execute(
        sa.text("SELECT relrowsecurity FROM pg_class WHERE relname = 'trace'")
    ).scalar()
    conn.execute(sa.text("ALTER TABLE trace DISABLE ROW LEVEL SECURITY"))
    _backfill(conn)
    if enabled:
        conn.execute(sa.text("ALTER TABLE trace ENABLE ROW LEVEL SECURITY"))


def _create_index() -> None:
    conn = op.get_bind()
    # A failed CONCURRENTLY build leaves an INVALID index that IF NOT EXISTS would
    # keep forever; drop it so the rerun rebuilds it.
    invalid = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
            "WHERE NOT i.indisvalid AND c.relname = :name"
        ),
        {"name": _INDEX},
    ).scalar()
    if invalid:
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
    op.execute(
        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX} "
        "ON trace (project_id, span_type, start_time DESC)"
    )


@contextmanager
def _autocommit_with_lock_timeout():
    # SET LOCAL dies with the transaction autocommit_block() commits, so the
    # timeout has to be set again, per session, for the work inside it.
    with op.get_context().autocommit_block():
        conn = op.get_bind()
        conn.execute(sa.text(f"SET lock_timeout = '{_LOCK_TIMEOUT}'"))
        try:
            yield conn
        finally:
            conn.execute(sa.text("RESET lock_timeout"))


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"SET LOCAL lock_timeout = '{_LOCK_TIMEOUT}'"))
    # The auto_rls_on_ddl event trigger's reentry guard: keeps it from touching
    # trace's policies (or its RLS switch) on the ALTER TABLEs below.
    conn.execute(sa.text("SET LOCAL auto_rls.active = 'true'"))
    _add_column(conn)

    if _has_bypassrls(conn):
        with _autocommit_with_lock_timeout() as autocommit_conn:
            _backfill(autocommit_conn)
    else:
        _backfill_under_rls(conn)
        conn.execute(sa.text("SET LOCAL auto_rls.active = 'false'"))

    # auto_rls.active isn't needed from here on: the event trigger ignores indexes.
    with _autocommit_with_lock_timeout():
        _create_index()


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
    op.drop_column("trace", "span_type")
