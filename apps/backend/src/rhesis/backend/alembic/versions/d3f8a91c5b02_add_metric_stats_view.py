from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f8a91c5b02"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Hardcoded lists of statuses to ensure migration stability. Kept in sync by hand
# with the copies in cb4b107b5daf_add_stats_views.py -- these mirror the constants
# at the time of this migration and must not be swapped for a live import.
_RESULT_PASSED_IN = (
    "('complete', 'completed', 'done', 'finished', 'pass', 'passed', 'success', 'successful')"
)
_RESULT_FAILED_IN = "('fail', 'failed')"

V_METRIC_STATS = f"""
CREATE OR REPLACE VIEW v_metric_stats AS
WITH unnested AS (
    SELECT
        trs.id             AS test_result_id,
        trs.organization_id,
        trs.test_run_id,
        trs.test_id,
        t.behavior_id,
        t.category_id,
        t.topic_id,
        trs.created_at,
        EXTRACT(YEAR  FROM trs.created_at)::int AS year,
        EXTRACT(MONTH FROM trs.created_at)::int AS month,
        CASE
            WHEN LOWER(s.name) IN {_RESULT_PASSED_IN} THEN 'passed'
            WHEN LOWER(s.name) IN {_RESULT_FAILED_IN} THEN 'failed'
            ELSE 'pending'
        END                AS overall_result,
        m.key              AS metric_name,
        (m.value ->> 'is_successful')::boolean AS is_successful,
        (m.value ? 'override')
            AND m.value -> 'override' <> 'null'::jsonb
            AND m.value -> 'override' <> '{{}}'::jsonb AS has_override,
        m.value #>> '{{override,original_value}}' AS override_original_value_raw
    FROM test_result trs
    JOIN test t   ON trs.test_id = t.id AND t.deleted_at IS NULL
    JOIN status s ON trs.status_id = s.id
    CROSS JOIN LATERAL jsonb_each(trs.test_metrics -> 'metrics') AS m(key, value)
    WHERE trs.deleted_at IS NULL
      AND m.value ? 'is_successful'
)
SELECT
    test_result_id,
    organization_id,
    test_run_id,
    test_id,
    behavior_id,
    category_id,
    topic_id,
    created_at,
    year,
    month,
    metric_name,
    has_override,
    -- Pre-review automated outcome: the override's stashed original value if
    -- present, otherwise the current (possibly overridden) is_successful.
    COALESCE(override_original_value_raw::boolean, is_successful) AS automated_success,
    -- Mirrors effective_metric_success() in services/stats/common.py: a metric
    -- override always wins; otherwise a disagreeing overall result overrides
    -- the stored per-metric value.
    CASE
        WHEN has_override THEN is_successful
        WHEN overall_result = 'passed' AND NOT is_successful THEN true
        WHEN overall_result = 'failed' AND is_successful THEN false
        ELSE is_successful
    END AS effective_success
FROM unnested
"""


def upgrade() -> None:
    op.execute(V_METRIC_STATS)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_metric_stats")
