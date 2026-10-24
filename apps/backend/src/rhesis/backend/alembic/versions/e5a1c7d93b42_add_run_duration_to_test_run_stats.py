"""Add a run duration to v_test_run_stats

Runs keep their timing in the attributes JSON, not in columns:
total_execution_time_ms once results are collected, and otherwise the
started_at and completed_at timestamps. The view exposes it as duration_ms so
the insights registry can report how long runs take. Runs that never started
or are still running have no duration (NULL), which the aggregates skip.

Revision ID: e5a1c7d93b42
Revises: b3e7c91d4a20
Create Date: 2026-10-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e5a1c7d93b42"
down_revision: Union[str, None] = "b3e7c91d4a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Values come from JSON, so each is checked before the cast: one malformed
# timestamp must not make every insights query on runs fail.
_DURATION_MS = r"""CASE
        WHEN tr.attributes->>'total_execution_time_ms' ~ '^[0-9]+(\.[0-9]+)?$'
            THEN CAST(tr.attributes->>'total_execution_time_ms' AS double precision)
        WHEN tr.attributes->>'started_at' ~ '^\d{4}-\d{2}-\d{2}T'
            AND tr.attributes->>'completed_at' ~ '^\d{4}-\d{2}-\d{2}T'
            THEN EXTRACT(EPOCH FROM (
                CAST(tr.attributes->>'completed_at' AS timestamptz)
                - CAST(tr.attributes->>'started_at' AS timestamptz)
            )) * 1000
    END"""


def _view(duration: str) -> str:
    return f"""
CREATE VIEW v_test_run_stats AS
SELECT tr.id AS test_run_id,
    tr.organization_id,
    tr.created_at,
    tr.user_id,
    tr.status_id,
    s.name AS status_name,
    CASE
        WHEN lower(s.name) IN ('complete', 'completed', 'done', 'finished', 'success', 'successful')
            THEN 'passed'
        WHEN lower(s.name) IN ('aborted', 'error', 'fail', 'failed') THEN 'failed'
        ELSE 'pending'
    END AS result,
    tc.test_set_id,
    tc.endpoint_id,
    ts.name AS test_set_name,
    e.name AS endpoint_name,
    COALESCE(u.email, u.name, CAST(u.id AS text)) AS executor_name{duration}
FROM test_run tr
JOIN status s ON tr.status_id = s.id
LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id
LEFT JOIN test_set ts ON tc.test_set_id = ts.id AND ts.deleted_at IS NULL
LEFT JOIN endpoint e ON tc.endpoint_id = e.id
LEFT JOIN "user" u ON tr.user_id = u.id
WHERE tr.deleted_at IS NULL
"""


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_test_run_stats")
    op.execute(_view(f",\n    {_DURATION_MS} AS duration_ms"))


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_test_run_stats")
    op.execute(_view(""))
