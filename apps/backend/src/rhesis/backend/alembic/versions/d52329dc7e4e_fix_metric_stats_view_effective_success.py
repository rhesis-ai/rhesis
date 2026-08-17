from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d52329dc7e4e"
down_revision: Union[str, None] = "b7e3a1c9d2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# effective_success previously fell back to the test's overall Pass/Fail whenever
# it disagreed with a metric's own is_successful. That overall status is itself an
# AND across all of a test's metrics, so on any test with mixed metric outcomes it
# disagreed with the passing metrics by construction -- one failing metric dragged
# every other (actually-passing) metric on that same test into "failed" in the
# aggregate stats. is_successful already carries the metric's own correct verdict,
# including a review that targeted that specific metric (see
# _apply_metric_override in services/review_override.py), so no fallback is needed.
V_METRIC_STATS_FIXED = """
CREATE OR REPLACE VIEW v_metric_stats AS
WITH unnested AS (
    SELECT
        trs.id             AS test_result_id,
        trs.organization_id,
        trs.test_run_id,
        trs.test_id,
        t.requirement_id,
        trs.created_at,
        EXTRACT(YEAR  FROM trs.created_at)::int AS year,
        EXTRACT(MONTH FROM trs.created_at)::int AS month,
        m.key              AS metric_name,
        (m.value ->> 'is_successful')::boolean AS is_successful,
        (m.value ? 'override')
            AND m.value -> 'override' <> 'null'::jsonb
            AND m.value -> 'override' <> '{}'::jsonb AS has_override,
        m.value #>> '{override,original_value}' AS override_original_value_raw
    FROM test_result trs
    JOIN test t   ON trs.test_id = t.id AND t.deleted_at IS NULL
    CROSS JOIN LATERAL jsonb_each(trs.test_metrics -> 'metrics') AS m(key, value)
    WHERE trs.deleted_at IS NULL
      AND m.value ? 'is_successful'
)
SELECT
    test_result_id,
    organization_id,
    test_run_id,
    test_id,
    requirement_id,
    created_at,
    year,
    month,
    metric_name,
    has_override,
    -- Pre-review automated outcome: the override's stashed original value if
    -- present, otherwise the current (possibly overridden) is_successful.
    COALESCE(override_original_value_raw::boolean, is_successful) AS automated_success,
    -- This metric's own recorded verdict (automated, or corrected by a review that
    -- targeted this specific metric). A whole-test review judges the response as a
    -- whole, not this metric's own correctness, so it's deliberately excluded here.
    is_successful AS effective_success
FROM unnested
"""

# Prior view definition (d3f8a91c5b02_add_metric_stats_view.py), restored on downgrade.
_RESULT_PASSED_IN = (
    "('complete', 'completed', 'done', 'finished', 'pass', 'passed', 'success', 'successful')"
)
_RESULT_FAILED_IN = "('fail', 'failed')"

V_METRIC_STATS_PREVIOUS = f"""
CREATE OR REPLACE VIEW v_metric_stats AS
WITH unnested AS (
    SELECT
        trs.id             AS test_result_id,
        trs.organization_id,
        trs.test_run_id,
        trs.test_id,
        t.requirement_id,
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
    requirement_id,
    created_at,
    year,
    month,
    metric_name,
    has_override,
    COALESCE(override_original_value_raw::boolean, is_successful) AS automated_success,
    CASE
        WHEN has_override THEN is_successful
        WHEN overall_result = 'passed' AND NOT is_successful THEN true
        WHEN overall_result = 'failed' AND is_successful THEN false
        ELSE is_successful
    END AS effective_success
FROM unnested
"""


def upgrade() -> None:
    op.execute(V_METRIC_STATS_FIXED)


def downgrade() -> None:
    op.execute(V_METRIC_STATS_PREVIOUS)
