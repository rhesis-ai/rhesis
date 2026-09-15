"""Backfill annotation rows from test_result.test_reviews and trace.trace_reviews

Each JSONB ``review_id`` becomes the annotation's primary key, so the override
markers inside ``test_metrics`` / ``trace_metrics`` (which keep the key
``review_id``) stay valid without touching that data. ``ON CONFLICT (id) DO
NOTHING`` makes the insert idempotent.

Reviews whose status or author no longer exists are skipped rather than aborting
the migration on a foreign key, and the counts printed per org say how many rows
landed.

``annotation``, ``test_result`` and ``trace`` all run under FORCE ROW LEVEL
SECURITY, so every statement here runs with the org GUC bound, one org at a time
(same approach as 9550c62e80a5).

Revision ID: a0004bkflanno
Revises: a0003annperms
Create Date: 2026-09-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a0004bkflanno"
down_revision: Union[str, None] = "a0003annperms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BIND_ORG = sa.text("""
    SELECT set_config('app.current_organization', :org_id, true),
           set_config('app.current_project', '', true)
""")

# Read before any org is bound: the organization table's policy is the one that
# tolerates an unset tenant GUC, every other table here requires it.
_ORGANIZATIONS = sa.text("SELECT id FROM organization WHERE deleted_at IS NULL")

# One template for both parents: they carry the same review JSONB shape and differ
# only in table, column and the entity_type stamped on the annotation.
_BACKFILL = """
    INSERT INTO annotation (
        id, organization_id, project_id, user_id,
        entity_type, entity_id, target_type, target_reference,
        status_id, comments, resolved, resolved_at, resolved_by_id,
        created_at, updated_at
    )
    SELECT
        CAST(r->>'review_id' AS uuid),
        p.organization_id,
        p.project_id,
        u.id,
        '{entity_type}',
        p.id,
        -- 'test' is the pre-c4d5e6f7a8b9 spelling of the entity-level target.
        CASE WHEN COALESCE(r->'target'->>'type', 'test') = 'test'
             THEN '{entity_target}'
             ELSE r->'target'->>'type'
        END,
        r->'target'->>'reference',
        s.id,
        r->>'comments',
        COALESCE(CAST(r->>'resolved' AS boolean), false),
        CAST(r->>'resolved_at' AS timestamp with time zone),
        rb.id,
        COALESCE(CAST(r->>'created_at' AS timestamp with time zone), now()),
        COALESCE(CAST(r->>'updated_at' AS timestamp with time zone), now())
    FROM {table} p
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(p.{column}->'reviews') = 'array'
             THEN p.{column}->'reviews' ELSE '[]'::jsonb END
    ) AS r
    JOIN status s ON s.id = CAST(r->'status'->>'status_id' AS uuid)
    JOIN "user" u ON u.id = CAST(r->'user'->>'user_id' AS uuid)
    LEFT JOIN "user" rb ON rb.id = CAST(r->'resolved_by'->>'user_id' AS uuid)
    WHERE p.organization_id = CAST(:org_id AS uuid)
      AND r->>'review_id' IS NOT NULL
    ON CONFLICT (id) DO NOTHING
"""

_SNAPSHOT_TEST_RESULT = sa.text("""
    UPDATE test_result
    SET original_status_id = CAST(test_reviews->'metadata'->>'original_status_id' AS uuid)
    WHERE organization_id = CAST(:org_id AS uuid)
      AND original_status_id IS NULL
      AND test_reviews->'metadata'->>'original_status_id' IS NOT NULL
""")

# Trace reviews never snapshotted the pre-review status, so the automated one is
# only recoverable for traces nobody overrode at the trace level.
_SNAPSHOT_TRACE = sa.text("""
    UPDATE trace
    SET original_status_id = trace_metrics_status_id
    WHERE organization_id = CAST(:org_id AS uuid)
      AND original_status_id IS NULL
      AND trace_metrics_status_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM annotation a
          WHERE a.entity_type = 'Trace'
            AND a.entity_id = trace.id
            AND a.target_type = 'trace'
            AND a.deleted_at IS NULL
      )
""")


def _rowcount(result) -> int:
    return result.rowcount if result.rowcount is not None else 0


_SOURCES = (
    {
        "table": "test_result",
        "column": "test_reviews",
        "entity_type": "TestResult",
        "entity_target": "test_result",
    },
    {
        "table": "trace",
        "column": "trace_reviews",
        "entity_type": "Trace",
        "entity_target": "trace",
    },
)


def upgrade() -> None:
    conn = op.get_bind()
    org_ids = [row[0] for row in conn.execute(_ORGANIZATIONS)]

    annotations = snapshots = 0
    for org_id in org_ids:
        params = {"org_id": str(org_id)}
        conn.execute(_BIND_ORG, params)

        inserted = sum(
            _rowcount(conn.execute(sa.text(_BACKFILL.format(**source)), params))
            for source in _SOURCES
        )
        snapshotted = _rowcount(conn.execute(_SNAPSHOT_TEST_RESULT, params)) + _rowcount(
            conn.execute(_SNAPSHOT_TRACE, params)
        )
        if inserted or snapshotted:
            print(
                f"[a0004bkflanno] org {org_id}: {inserted} annotation(s), "
                f"{snapshotted} original_status_id snapshot(s)."
            )
        annotations += inserted
        snapshots += snapshotted

    print(
        f"[a0004bkflanno] Backfilled {annotations} annotation(s) and {snapshots} "
        f"snapshot(s) across {len(org_ids)} organization(s)."
    )


def downgrade() -> None:
    conn = op.get_bind()
    for org_id in [row[0] for row in conn.execute(_ORGANIZATIONS)]:
        params = {"org_id": str(org_id)}
        conn.execute(_BIND_ORG, params)
        # Only the rows this migration created: their ids are the JSONB review ids.
        for source in _SOURCES:
            conn.execute(
                sa.text(
                    """
                    DELETE FROM annotation
                    WHERE organization_id = CAST(:org_id AS uuid)
                      AND id IN (
                          SELECT CAST(r->>'review_id' AS uuid)
                          FROM {table} p
                          CROSS JOIN LATERAL jsonb_array_elements(
                              CASE WHEN jsonb_typeof(p.{column}->'reviews') = 'array'
                                   THEN p.{column}->'reviews' ELSE '[]'::jsonb END
                          ) AS r
                          WHERE p.organization_id = CAST(:org_id AS uuid)
                            AND r->>'review_id' IS NOT NULL
                      )
                """.format(**source)
                ),
                params,
            )
        conn.execute(
            sa.text(
                "UPDATE test_result SET original_status_id = NULL "
                "WHERE organization_id = CAST(:org_id AS uuid)"
            ),
            params,
        )
        conn.execute(
            sa.text(
                "UPDATE trace SET original_status_id = NULL "
                "WHERE organization_id = CAST(:org_id AS uuid)"
            ),
            params,
        )
