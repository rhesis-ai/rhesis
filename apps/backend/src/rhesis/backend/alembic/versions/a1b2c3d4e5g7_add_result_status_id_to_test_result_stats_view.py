"""add result_status_id to v_test_result_stats

The view exposes the test's lifecycle status (t.status_id) as test_status_id
but never exposes the test result's own status (trs.status_id). The insights
status filter sends test-result status UUIDs (Error/Fail/Pass/Review), which
were matched against the wrong column and always returned zero rows.

Revision ID: a1b2c3d4e5g7
Revises: 40a5b6b88a52
Create Date: 2026-08-20

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5g7"
down_revision: Union[str, None] = "40a5b6b88a52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RESULT_PASSED_IN = (
    "('complete', 'completed', 'done', 'finished', 'pass', 'passed', 'success', 'successful')"
)
_RESULT_FAILED_IN = "('fail', 'failed')"

V_TEST_RESULT_STATS_UP = f"""
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
    trs.status_id    AS result_status_id,
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

V_TEST_RESULT_STATS_DOWN = f"""
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
    op.execute(V_TEST_RESULT_STATS_UP)


def downgrade() -> None:
    op.execute(V_TEST_RESULT_STATS_DOWN)
