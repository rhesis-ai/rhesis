"""Redesign the insights stats views

Adds the columns the redesigned insights registry groups and filters by:
test set, endpoint and executor on results and metrics; topic, category,
requirement and run names plus a numeric score on metrics; status id and
endpoint name on runs.

Drops year/month from every view. The registry now buckets created_at itself
(period + time_grain, always UTC), which also ends v_metric_stats and
v_test_stats bucketing in the session timezone while the other two used UTC.

Revision ID: b3e7c91d4a20
Revises: d7a3e9b2c4f1
Create Date: 2026-10-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b3e7c91d4a20"
down_revision: Union[str, None] = "d7a3e9b2c4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VIEWS = ("v_test_result_stats", "v_metric_stats", "v_test_run_stats", "v_test_stats")

_RESULT_CASE = """CASE
        WHEN trs.execution = 'ok' AND trs.verdict = 'pass' THEN 'passed'
        WHEN trs.execution = 'ok' AND trs.verdict = 'fail' THEN 'failed'
        WHEN trs.execution = 'error' THEN 'error'
        WHEN trs.execution = 'cancelled' THEN 'cancelled'
        ELSE 'pending'
    END"""

V_TEST_RESULT_STATS = f"""
CREATE VIEW v_test_result_stats AS
SELECT trs.id AS test_result_id,
    trs.organization_id,
    trs.created_at,
    trs.test_run_id,
    trs.test_id,
    trs.test_metrics,
    s.name AS status_name,
    {_RESULT_CASE} AS result,
    trs.status_id AS result_status_id,
    t.status_id AS test_status_id,
    t.requirement_id,
    t.category_id,
    t.topic_id,
    t.user_id AS test_user_id,
    t.assignee_id,
    t.owner_id,
    t.prompt_id,
    t.priority,
    t.test_type_id,
    r.name AS requirement_name,
    c.name AS category_name,
    tp.name AS topic_name,
    tr.id AS run_id,
    tr.name AS test_run_name,
    tr.created_at AS test_run_created_at,
    tc.test_set_id,
    ts.name AS test_set_name,
    tc.endpoint_id,
    e.name AS endpoint_name,
    tr.user_id AS executor_id,
    COALESCE(u.email, u.name, CAST(u.id AS text)) AS executor_name
FROM test_result trs
JOIN test t ON trs.test_id = t.id AND t.deleted_at IS NULL
JOIN status s ON trs.status_id = s.id
LEFT JOIN requirement r ON t.requirement_id = r.id
LEFT JOIN category c ON t.category_id = c.id
LEFT JOIN topic tp ON t.topic_id = tp.id
LEFT JOIN test_run tr ON trs.test_run_id = tr.id
LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id
LEFT JOIN test_set ts ON tc.test_set_id = ts.id AND ts.deleted_at IS NULL
LEFT JOIN endpoint e ON tc.endpoint_id = e.id
LEFT JOIN "user" u ON tr.user_id = u.id
WHERE trs.deleted_at IS NULL
"""

V_METRIC_STATS = """
CREATE VIEW v_metric_stats AS
WITH unnested AS (
    SELECT trs.id AS test_result_id,
        trs.organization_id,
        trs.test_run_id,
        trs.test_id,
        t.requirement_id,
        t.topic_id,
        t.category_id,
        r.name AS requirement_name,
        tp.name AS topic_name,
        c.name AS category_name,
        tr.name AS test_run_name,
        tc.test_set_id,
        ts.name AS test_set_name,
        tc.endpoint_id,
        e.name AS endpoint_name,
        trs.created_at,
        m.key AS metric_name,
        CAST(m.value ->> 'is_successful' AS boolean) AS is_successful,
        m.value ? 'override'
            AND m.value -> 'override' <> 'null'::jsonb
            AND m.value -> 'override' <> '{}'::jsonb AS has_override,
        m.value #>> '{override,original_value}' AS override_original_value_raw,
        -- Categorical scores ("polite") stay NULL so they never reach an average.
        CASE WHEN jsonb_typeof(m.value -> 'score') = 'number'
            THEN CAST(m.value ->> 'score' AS double precision)
        END AS score
    FROM test_result trs
    JOIN test t ON trs.test_id = t.id AND t.deleted_at IS NULL
    LEFT JOIN requirement r ON t.requirement_id = r.id
    LEFT JOIN topic tp ON t.topic_id = tp.id
    LEFT JOIN category c ON t.category_id = c.id
    LEFT JOIN test_run tr ON trs.test_run_id = tr.id
    LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id
    LEFT JOIN test_set ts ON tc.test_set_id = ts.id AND ts.deleted_at IS NULL
    LEFT JOIN endpoint e ON tc.endpoint_id = e.id
    CROSS JOIN LATERAL jsonb_each(trs.test_metrics -> 'metrics') AS m(key, value)
    WHERE trs.deleted_at IS NULL
      AND m.value ? 'is_successful'
)
SELECT test_result_id,
    organization_id,
    test_run_id,
    test_id,
    requirement_id,
    created_at,
    metric_name,
    has_override,
    COALESCE(CAST(override_original_value_raw AS boolean), is_successful) AS automated_success,
    is_successful AS effective_success,
    topic_id,
    category_id,
    requirement_name,
    topic_name,
    category_name,
    test_run_name,
    test_set_id,
    test_set_name,
    endpoint_id,
    endpoint_name,
    score
FROM unnested
"""

# result is the run's own completion (from its status), not its tests' verdicts.
V_TEST_RUN_STATS = """
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
    COALESCE(u.email, u.name, CAST(u.id AS text)) AS executor_name
FROM test_run tr
JOIN status s ON tr.status_id = s.id
LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id
LEFT JOIN test_set ts ON tc.test_set_id = ts.id AND ts.deleted_at IS NULL
LEFT JOIN endpoint e ON tc.endpoint_id = e.id
LEFT JOIN "user" u ON tr.user_id = u.id
WHERE tr.deleted_at IS NULL
"""

V_TEST_STATS = f"""
CREATE VIEW v_test_stats AS
WITH results AS (
    SELECT trs.test_id,
        trs.created_at,
        {_RESULT_CASE} AS result
    FROM test_result trs
    WHERE trs.deleted_at IS NULL
), agg AS (
    SELECT results.test_id,
        count(*) AS run_count,
        count(*) FILTER (WHERE results.result = 'passed') AS passed_count,
        count(*) FILTER (WHERE results.result = 'failed') AS failed_count,
        count(*) FILTER (WHERE results.result IN ('pending', 'cancelled')) AS pending_count,
        count(*) FILTER (WHERE results.result = 'error') AS error_count,
        max(results.created_at) AS last_run_at
    FROM results
    GROUP BY results.test_id
)
SELECT t.id AS test_id,
    t.organization_id,
    t.requirement_id,
    t.category_id,
    t.topic_id,
    t.test_type_id,
    t.user_id AS test_user_id,
    t.assignee_id,
    t.owner_id,
    t.prompt_id,
    t.priority,
    t.status_id AS test_status_id,
    r.name AS requirement_name,
    c.name AS category_name,
    tp.name AS topic_name,
    t.created_at,
    COALESCE(agg.run_count, 0) AS run_count,
    COALESCE(agg.passed_count, 0) AS passed_count,
    COALESCE(agg.failed_count, 0) AS failed_count,
    COALESCE(agg.pending_count, 0) AS pending_count,
    agg.run_count IS NULL OR agg.run_count = 0 AS is_unrun,
    agg.last_run_at,
    COALESCE(agg.error_count, 0) AS error_count
FROM test t
LEFT JOIN agg ON agg.test_id = t.id
LEFT JOIN requirement r ON t.requirement_id = r.id
LEFT JOIN category c ON t.category_id = c.id
LEFT JOIN topic tp ON t.topic_id = tp.id
WHERE t.deleted_at IS NULL
"""

# The definitions this migration replaces, as pg_get_viewdef printed them at d7a3e9b2c4f1.
_DOWN_TEST_RESULT_STATS = f"""
CREATE VIEW v_test_result_stats AS
SELECT trs.id AS test_result_id,
    trs.organization_id,
    trs.created_at,
    trs.test_run_id,
    trs.test_id,
    trs.test_metrics,
    s.name AS status_name,
    {_RESULT_CASE} AS result,
    trs.status_id AS result_status_id,
    t.status_id AS test_status_id,
    t.requirement_id,
    t.category_id,
    t.topic_id,
    t.user_id AS test_user_id,
    t.assignee_id,
    t.owner_id,
    t.prompt_id,
    t.priority,
    t.test_type_id,
    r.name AS requirement_name,
    c.name AS category_name,
    tp.name AS topic_name,
    tr.id AS run_id,
    tr.name AS test_run_name,
    tr.created_at AS test_run_created_at,
    CAST(EXTRACT(year FROM (trs.created_at AT TIME ZONE 'UTC')) AS integer) AS year,
    CAST(EXTRACT(month FROM (trs.created_at AT TIME ZONE 'UTC')) AS integer) AS month
FROM test_result trs
JOIN test t ON trs.test_id = t.id AND t.deleted_at IS NULL
JOIN status s ON trs.status_id = s.id
LEFT JOIN requirement r ON t.requirement_id = r.id
LEFT JOIN category c ON t.category_id = c.id
LEFT JOIN topic tp ON t.topic_id = tp.id
LEFT JOIN test_run tr ON trs.test_run_id = tr.id
WHERE trs.deleted_at IS NULL
"""

_DOWN_METRIC_STATS = """
CREATE VIEW v_metric_stats AS
WITH unnested AS (
    SELECT trs.id AS test_result_id,
        trs.organization_id,
        trs.test_run_id,
        trs.test_id,
        t.requirement_id,
        trs.created_at,
        CAST(EXTRACT(year FROM trs.created_at) AS integer) AS year,
        CAST(EXTRACT(month FROM trs.created_at) AS integer) AS month,
        m.key AS metric_name,
        CAST(m.value ->> 'is_successful' AS boolean) AS is_successful,
        m.value ? 'override'
            AND m.value -> 'override' <> 'null'::jsonb
            AND m.value -> 'override' <> '{}'::jsonb AS has_override,
        m.value #>> '{override,original_value}' AS override_original_value_raw
    FROM test_result trs
    JOIN test t ON trs.test_id = t.id AND t.deleted_at IS NULL
    CROSS JOIN LATERAL jsonb_each(trs.test_metrics -> 'metrics') AS m(key, value)
    WHERE trs.deleted_at IS NULL
      AND m.value ? 'is_successful'
)
SELECT test_result_id,
    organization_id,
    test_run_id,
    test_id,
    requirement_id,
    created_at,
    year,
    month,
    metric_name,
    has_override,
    COALESCE(CAST(override_original_value_raw AS boolean), is_successful) AS automated_success,
    is_successful AS effective_success
FROM unnested
"""

_DOWN_TEST_RUN_STATS = """
CREATE VIEW v_test_run_stats AS
SELECT tr.id AS test_run_id,
    tr.organization_id,
    tr.created_at,
    tr.user_id,
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
    COALESCE(u.email, u.name, CAST(u.id AS text)) AS executor_name,
    CAST(EXTRACT(year FROM (tr.created_at AT TIME ZONE 'UTC')) AS integer) AS year,
    CAST(EXTRACT(month FROM (tr.created_at AT TIME ZONE 'UTC')) AS integer) AS month
FROM test_run tr
JOIN status s ON tr.status_id = s.id
LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id
LEFT JOIN test_set ts ON tc.test_set_id = ts.id AND ts.deleted_at IS NULL
LEFT JOIN "user" u ON tr.user_id = u.id
WHERE tr.deleted_at IS NULL
"""

_DOWN_TEST_STATS = f"""
CREATE VIEW v_test_stats AS
WITH results AS (
    SELECT trs.test_id,
        trs.created_at,
        {_RESULT_CASE} AS result
    FROM test_result trs
    WHERE trs.deleted_at IS NULL
), agg AS (
    SELECT results.test_id,
        count(*) AS run_count,
        count(*) FILTER (WHERE results.result = 'passed') AS passed_count,
        count(*) FILTER (WHERE results.result = 'failed') AS failed_count,
        count(*) FILTER (WHERE results.result IN ('pending', 'cancelled')) AS pending_count,
        count(*) FILTER (WHERE results.result = 'error') AS error_count,
        max(results.created_at) AS last_run_at
    FROM results
    GROUP BY results.test_id
)
SELECT t.id AS test_id,
    t.organization_id,
    t.requirement_id,
    t.category_id,
    t.topic_id,
    t.test_type_id,
    t.user_id AS test_user_id,
    t.assignee_id,
    t.owner_id,
    t.prompt_id,
    t.priority,
    t.status_id AS test_status_id,
    r.name AS requirement_name,
    c.name AS category_name,
    tp.name AS topic_name,
    t.created_at,
    CAST(EXTRACT(year FROM t.created_at) AS integer) AS year,
    CAST(EXTRACT(month FROM t.created_at) AS integer) AS month,
    COALESCE(agg.run_count, 0) AS run_count,
    COALESCE(agg.passed_count, 0) AS passed_count,
    COALESCE(agg.failed_count, 0) AS failed_count,
    COALESCE(agg.pending_count, 0) AS pending_count,
    agg.run_count IS NULL OR agg.run_count = 0 AS is_unrun,
    agg.last_run_at,
    COALESCE(agg.error_count, 0) AS error_count
FROM test t
LEFT JOIN agg ON agg.test_id = t.id
LEFT JOIN requirement r ON t.requirement_id = r.id
LEFT JOIN category c ON t.category_id = c.id
LEFT JOIN topic tp ON t.topic_id = tp.id
WHERE t.deleted_at IS NULL
"""


def _drop_views() -> None:
    for view in _VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {view}")


def upgrade() -> None:
    _drop_views()
    for ddl in (V_TEST_RESULT_STATS, V_METRIC_STATS, V_TEST_RUN_STATS, V_TEST_STATS):
        op.execute(ddl)


def downgrade() -> None:
    _drop_views()
    for ddl in (
        _DOWN_TEST_RESULT_STATS,
        _DOWN_METRIC_STATS,
        _DOWN_TEST_RUN_STATS,
        _DOWN_TEST_STATS,
    ):
        op.execute(ddl)
