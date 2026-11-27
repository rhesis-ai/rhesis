"""Add trace.agent_path and trace.is_root

Each span's agent path names the agent spans above it, outermost first, so a target's
``within`` can match in SQL (``agent_path @> ARRAY[:agent]``) instead of walking the tree.
``is_root`` says whether the span's parent is missing from its trace, the root rule the SDK's
span tree uses, so a target's turns and runs don't look the parent up for every span.
Ingest and span moves keep both with ``crud.telemetry.update_agent_paths``; this migration
backfills them with a frozen copy of that SQL. Change both together --
tests/backend/crud/test_trace_agent_path.py runs them against the same traces.

No index: under row-level security the planner can't use one for ``@>`` (not leakproof),
and ``is_root`` is read alongside conditions the existing indexes serve.

The columns are nullable, so adding them rewrites nothing. The ALTER commits before the
backfill, so ingest isn't blocked behind its lock while the backfill runs. The backfill
walks every tenant scope and recomputes a batch of traces per statement: one
project-wide recursive UPDATE took 14.5 minutes for 200k spans. Traces whose spans all
have both values are skipped, so a rerun only does what's left.

Revision ID: 1924e6ab1c6f
Revises: b6f1d3a8c9e2
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.idempotency import column_exists
from rhesis.backend.alembic.utils.tenant_scope import iter_tenant_scopes

revision: str = "1924e6ab1c6f"
down_revision: Union[str, None] = "b6f1d3a8c9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BATCH_SIZE = 500
_LOCK_TIMEOUT = "120s"

_PENDING = sa.text("""
    SELECT DISTINCT trace_id FROM trace
    WHERE organization_id = CAST(:org_id AS uuid)
      AND project_id = CAST(:project_id AS uuid)
      AND (agent_path IS NULL OR is_root IS NULL)
    ORDER BY trace_id
""")

# Mirrors crud.telemetry.update_agent_paths -- migrations can't import app code.
_UPDATE_AGENT_PATHS = sa.text("""
    WITH RECURSIVE spans AS (
        SELECT id, trace_id, span_id, parent_span_id,
               CASE WHEN span_type = 'agent.invoke' THEN coalesce(
                   CASE WHEN jsonb_typeof(attributes -> 'ai.tool.name') = 'string'
                             AND attributes ->> 'ai.tool.name' <> ''
                        THEN attributes ->> 'ai.tool.name' END,
                   CASE WHEN jsonb_typeof(attributes -> 'ai.agent.name') = 'string'
                             AND attributes ->> 'ai.agent.name' <> ''
                        THEN attributes ->> 'ai.agent.name' END,
                   CASE WHEN jsonb_typeof(attributes -> 'ai.model.name') = 'string'
                             AND attributes ->> 'ai.model.name' <> ''
                        THEN attributes ->> 'ai.model.name' END,
                   span_name, '')
               END AS agent_name
        FROM trace
        WHERE organization_id = CAST(:org_id AS uuid)
          AND project_id = CAST(:project_id AS uuid)
          AND trace_id = ANY(CAST(:trace_ids AS text[]))
    ),
    walk AS (
        SELECT s.id, s.trace_id, s.span_id, s.agent_name,
               CAST(ARRAY[] AS text[]) AS path, 1 AS depth
        FROM spans s
        WHERE NOT EXISTS (
            SELECT 1 FROM spans p
            WHERE p.trace_id = s.trace_id AND p.span_id = s.parent_span_id
        )
        UNION ALL
        SELECT c.id, c.trace_id, c.span_id, c.agent_name,
               CASE WHEN w.agent_name IS NULL THEN w.path ELSE w.path || w.agent_name END,
               w.depth + 1
        FROM walk w
        JOIN spans c ON c.trace_id = w.trace_id AND c.parent_span_id = w.span_id
        WHERE w.depth < 1000
    ),
    paths AS (
        SELECT s.id, coalesce(w.path, CAST(ARRAY[] AS text[])) AS path,
               NOT EXISTS (
                   SELECT 1 FROM spans p
                   WHERE p.trace_id = s.trace_id AND p.span_id = s.parent_span_id
               ) AS is_root
        FROM spans s LEFT JOIN walk w ON w.id = s.id
    )
    UPDATE trace t SET agent_path = paths.path, is_root = paths.is_root
    FROM paths
    WHERE t.id = paths.id
      AND (t.agent_path IS DISTINCT FROM paths.path OR t.is_root IS DISTINCT FROM paths.is_root)
""")


def _backfill_scope(conn, org_id: str, project_id: str, batch_size: int = _BATCH_SIZE) -> int:
    """Fill the paths and roots of one project's traces that lack them, a batch of traces at
    a time. Returns the spans written."""
    scope = {"org_id": org_id, "project_id": project_id}
    trace_ids = [row[0] for row in conn.execute(_PENDING, scope)]
    written = 0
    for start in range(0, len(trace_ids), batch_size):
        result = conn.execute(
            _UPDATE_AGENT_PATHS, {**scope, "trace_ids": trace_ids[start : start + batch_size]}
        )
        written += result.rowcount
    return written


def _backfill(conn, batch_size: int = _BATCH_SIZE) -> int:
    written = 0
    for org_id, project_id in iter_tenant_scopes(conn):
        # trace.project_id is NOT NULL: the org-only scope holds no spans.
        if project_id is not None:
            written += _backfill_scope(conn, org_id, project_id, batch_size)
    return written


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"SET LOCAL lock_timeout = '{_LOCK_TIMEOUT}'"))
    if not column_exists(conn, "trace", "agent_path"):
        op.add_column("trace", sa.Column("agent_path", sa.ARRAY(sa.Text()), nullable=True))
    if not column_exists(conn, "trace", "is_root"):
        op.add_column("trace", sa.Column("is_root", sa.Boolean(), nullable=True))
    # Commits the ALTER, so its lock isn't held through the backfill.
    with op.get_context().autocommit_block():
        pass

    _backfill(op.get_bind())


def downgrade() -> None:
    op.drop_column("trace", "is_root")
    op.drop_column("trace", "agent_path")
