from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "90104949ab99"
down_revision: Union[str, None] = "d3f8a91c5b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Hardcoded lists of statuses to ensure migration stability. Kept in sync by hand
# with the copies in cb4b107b5daf_add_stats_views.py / d3f8a91c5b02_add_metric_stats_view.py
# -- these mirror the constants at the time of this migration and must not be
# swapped for a live import.
_RESULT_PASSED_IN = (
    "('complete', 'completed', 'done', 'finished', 'pass', 'passed', 'success', 'successful')"
)
_RESULT_FAILED_IN = "('fail', 'failed')"

V_TEST_STATS = f"""
CREATE OR REPLACE VIEW v_test_stats AS
WITH results AS (
    SELECT
        trs.test_id,
        trs.created_at,
        CASE
            WHEN LOWER(s.name) IN {_RESULT_PASSED_IN} THEN 'passed'
            WHEN LOWER(s.name) IN {_RESULT_FAILED_IN} THEN 'failed'
            ELSE 'pending'
        END AS result
    FROM test_result trs
    JOIN status s ON trs.status_id = s.id
    WHERE trs.deleted_at IS NULL
),
agg AS (
    SELECT
        test_id,
        COUNT(*)                                    AS run_count,
        COUNT(*) FILTER (WHERE result = 'passed')   AS passed_count,
        COUNT(*) FILTER (WHERE result = 'failed')   AS failed_count,
        COUNT(*) FILTER (WHERE result = 'pending')  AS pending_count,
        MAX(created_at)                             AS last_run_at
    FROM results
    GROUP BY test_id
)
SELECT
    t.id            AS test_id,
    t.organization_id,
    t.behavior_id,
    t.category_id,
    t.topic_id,
    t.test_type_id,
    t.user_id       AS test_user_id,
    t.assignee_id,
    t.owner_id,
    t.prompt_id,
    t.priority,
    t.status_id     AS test_status_id,
    t.created_at,
    EXTRACT(YEAR  FROM t.created_at)::int AS year,
    EXTRACT(MONTH FROM t.created_at)::int AS month,
    COALESCE(agg.run_count, 0)     AS run_count,
    COALESCE(agg.passed_count, 0)  AS passed_count,
    COALESCE(agg.failed_count, 0)  AS failed_count,
    COALESCE(agg.pending_count, 0) AS pending_count,
    -- A test with zero non-deleted test_result rows -- never executed, so it
    -- has no pass/fail outcome to report. This is the row the old
    -- test_result-anchored views structurally can't produce.
    (agg.run_count IS NULL OR agg.run_count = 0) AS is_unrun,
    agg.last_run_at
FROM test t
LEFT JOIN agg ON agg.test_id = t.id
WHERE t.deleted_at IS NULL
"""


def upgrade() -> None:
    op.execute(V_TEST_STATS)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_test_stats")
