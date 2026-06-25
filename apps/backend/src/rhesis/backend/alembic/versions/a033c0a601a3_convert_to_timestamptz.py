from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a033c0a601a3"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RUN_PASSED_IN = "('complete', 'completed', 'done', 'finished', 'success', 'successful')"
_RUN_FAILED_IN = "('aborted', 'error', 'fail', 'failed')"
_RESULT_PASSED_IN = (
    "('complete', 'completed', 'done', 'finished', 'pass', 'passed', 'success', 'successful')"
)
_RESULT_FAILED_IN = "('fail', 'failed')"

V_TEST_RUN_STATS = f"""
CREATE OR REPLACE VIEW v_test_run_stats AS
SELECT
    tr.id            AS test_run_id,
    tr.organization_id,
    tr.created_at,
    tr.user_id,
    s.name           AS status_name,
    CASE
        WHEN LOWER(s.name) IN {_RUN_PASSED_IN} THEN 'passed'
        WHEN LOWER(s.name) IN {_RUN_FAILED_IN} THEN 'failed'
        ELSE 'pending'
    END              AS result,
    tc.test_set_id,
    tc.endpoint_id,
    ts.name          AS test_set_name,
    COALESCE(u.email, u.name, u.id::text) AS executor_name,
    EXTRACT(YEAR  FROM tr.created_at AT TIME ZONE 'UTC')::int AS year,
    EXTRACT(MONTH FROM tr.created_at AT TIME ZONE 'UTC')::int AS month
FROM test_run tr
JOIN status s ON tr.status_id = s.id
LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id
LEFT JOIN test_set ts ON tc.test_set_id = ts.id AND ts.deleted_at IS NULL
LEFT JOIN "user" u ON tr.user_id = u.id
WHERE tr.deleted_at IS NULL
"""

V_TEST_RESULT_STATS = f"""
CREATE OR REPLACE VIEW v_test_result_stats AS
SELECT
    trs.id           AS test_result_id,
    trs.organization_id,
    trs.created_at,
    trs.test_run_id,
    trs.test_id,
    trs.test_metrics,
    s.name           AS status_name,
    CASE
        WHEN LOWER(s.name) IN {_RESULT_PASSED_IN}
            THEN 'passed'
        WHEN LOWER(s.name) IN {_RESULT_FAILED_IN}
            THEN 'failed'
        ELSE 'pending'
    END              AS result,
    t.status_id      AS test_status_id,
    t.behavior_id,
    t.category_id,
    t.topic_id,
    t.user_id        AS test_user_id,
    t.assignee_id,
    t.owner_id,
    t.prompt_id,
    t.priority,
    t.test_type_id,
    b.name           AS behavior_name,
    c.name           AS category_name,
    tp.name          AS topic_name,
    tr.id            AS run_id,
    tr.name          AS test_run_name,
    tr.created_at    AS test_run_created_at,
    EXTRACT(YEAR  FROM trs.created_at AT TIME ZONE 'UTC')::int AS year,
    EXTRACT(MONTH FROM trs.created_at AT TIME ZONE 'UTC')::int AS month
FROM test_result trs
JOIN test t    ON trs.test_id = t.id AND t.deleted_at IS NULL
JOIN status s  ON trs.status_id = s.id
LEFT JOIN behavior b  ON t.behavior_id = b.id
LEFT JOIN category c  ON t.category_id = c.id
LEFT JOIN topic tp    ON t.topic_id    = tp.id
LEFT JOIN test_run tr ON trs.test_run_id = tr.id
WHERE trs.deleted_at IS NULL
"""


def upgrade() -> None:
    # Drop views that depend on timestamp columns first
    op.execute("DROP VIEW IF EXISTS v_test_result_stats")
    op.execute("DROP VIEW IF EXISTS v_test_run_stats")

    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # PostgreSQL skips the (very expensive) full-table rewrite when converting
    # ``timestamp`` -> ``timestamptz`` *only* if the session TimeZone is UTC and
    # no ``USING`` expression is supplied. Stored values are already UTC, so the
    # default cast under TimeZone=UTC is binary-identical to the old explicit
    # ``AT TIME ZONE 'UTC'`` clause — same data, but a metadata-only change
    # instead of rewriting huge tables (e.g. ``trace``, ``test_result``), which
    # previously timed out the Cloud Run migrate job. Save/restore the timezone
    # because alembic runs the whole batch in one transaction/connection.
    original_tz = conn.exec_driver_sql("SHOW timezone").scalar()
    op.execute("SET TIME ZONE 'UTC'")
    try:
        for table_name in inspector.get_table_names(schema="public"):
            for column in inspector.get_columns(table_name, schema="public"):
                if (
                    column["type"].__class__.__name__ == "TIMESTAMP"
                    and not column["type"].timezone
                ):
                    print(f"Converting {table_name}.{column['name']} to TIMESTAMPTZ")
                    op.alter_column(
                        table_name,
                        column["name"],
                        type_=sa.DateTime(timezone=True),
                    )
    finally:
        op.execute(f"SET TIME ZONE '{original_tz}'")

    # Recreate views
    op.execute(V_TEST_RUN_STATS)
    op.execute(V_TEST_RESULT_STATS)


def downgrade() -> None:
    # Drop views before reverting column types
    op.execute("DROP VIEW IF EXISTS v_test_result_stats")
    op.execute("DROP VIEW IF EXISTS v_test_run_stats")

    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Mirror the upgrade: with TimeZone=UTC and no USING clause the reverse
    # conversion (timestamptz -> timestamp) is also a metadata-only change.
    original_tz = conn.exec_driver_sql("SHOW timezone").scalar()
    op.execute("SET TIME ZONE 'UTC'")
    try:
        for table_name in inspector.get_table_names(schema="public"):
            for column in inspector.get_columns(table_name, schema="public"):
                if (
                    column["type"].__class__.__name__ == "TIMESTAMP"
                    and column["type"].timezone
                ):
                    print(f"Reverting {table_name}.{column['name']} to TIMESTAMP")
                    op.alter_column(
                        table_name,
                        column["name"],
                        type_=sa.DateTime(timezone=False),
                    )
    finally:
        op.execute(f"SET TIME ZONE '{original_tz}'")

    # Recreate views
    op.execute(V_TEST_RUN_STATS)
    op.execute(V_TEST_RESULT_STATS)
