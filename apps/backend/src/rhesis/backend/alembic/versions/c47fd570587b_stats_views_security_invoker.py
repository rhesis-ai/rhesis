"""Run the stats views as the caller and match organizations in their joins

A view runs with its owner's privileges by default, and the owner is the
migration role, which bypasses row level security. So the stats views read
every organization's rows, and their joins could pair a test_result with a
test (or run, test set, endpoint...) from another organization.

The views are now created WITH (security_invoker = true), so the RLS policies
of the underlying tables apply to whoever queries them, and every join also
requires the same organization_id, which holds even for roles that bypass RLS.
v_test_stats groups results per (test, organization) for the same reason.

The definitions are otherwise those of b3e7c91d4a20 and e5a1c7d93b42.

Revision ID: c47fd570587b
Revises: db8b66e257cc
Create Date: 2026-11-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c47fd570587b"
down_revision: Union[str, None] = "db8b66e257cc"
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

_DURATION_MS = """CASE
        WHEN pg_input_is_valid(tr.attributes->>'total_execution_time_ms', 'double precision')
            THEN CAST(tr.attributes->>'total_execution_time_ms' AS double precision)
        WHEN pg_input_is_valid(tr.attributes->>'started_at', 'timestamptz')
            AND pg_input_is_valid(tr.attributes->>'completed_at', 'timestamptz')
            THEN EXTRACT(EPOCH FROM (
                CAST(tr.attributes->>'completed_at' AS timestamptz)
                - CAST(tr.attributes->>'started_at' AS timestamptz)
            )) * 1000
    END"""


def _org(alias: str, anchor: str, secure: bool) -> str:
    return f" AND {alias}.organization_id = {anchor}.organization_id" if secure else ""


def _with(secure: bool) -> str:
    return " WITH (security_invoker = true)" if secure else ""


def _test_result_stats(secure: bool) -> str:
    def o(alias: str) -> str:
        return _org(alias, "trs", secure)

    return f"""
CREATE VIEW v_test_result_stats{_with(secure)} AS
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
JOIN test t ON trs.test_id = t.id{o("t")} AND t.deleted_at IS NULL
JOIN status s ON trs.status_id = s.id{o("s")}
LEFT JOIN requirement r ON t.requirement_id = r.id{o("r")}
LEFT JOIN category c ON t.category_id = c.id{o("c")}
LEFT JOIN topic tp ON t.topic_id = tp.id{o("tp")}
LEFT JOIN test_run tr ON trs.test_run_id = tr.id{o("tr")}
LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id{o("tc")}
LEFT JOIN test_set ts ON tc.test_set_id = ts.id{o("ts")} AND ts.deleted_at IS NULL
LEFT JOIN endpoint e ON tc.endpoint_id = e.id{o("e")}
LEFT JOIN "user" u ON tr.user_id = u.id
WHERE trs.deleted_at IS NULL
"""


def _metric_stats(secure: bool) -> str:
    def o(alias: str) -> str:
        return _org(alias, "trs", secure)

    return f"""
CREATE VIEW v_metric_stats{_with(secure)} AS
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
            AND m.value -> 'override' <> '{{}}'::jsonb AS has_override,
        m.value #>> '{{override,original_value}}' AS override_original_value_raw,
        -- Categorical scores ("polite") stay NULL so they never reach an average.
        CASE WHEN jsonb_typeof(m.value -> 'score') = 'number'
            THEN CAST(m.value ->> 'score' AS double precision)
        END AS score
    FROM test_result trs
    JOIN test t ON trs.test_id = t.id{o("t")} AND t.deleted_at IS NULL
    LEFT JOIN requirement r ON t.requirement_id = r.id{o("r")}
    LEFT JOIN topic tp ON t.topic_id = tp.id{o("tp")}
    LEFT JOIN category c ON t.category_id = c.id{o("c")}
    LEFT JOIN test_run tr ON trs.test_run_id = tr.id{o("tr")}
    LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id{o("tc")}
    LEFT JOIN test_set ts ON tc.test_set_id = ts.id{o("ts")} AND ts.deleted_at IS NULL
    LEFT JOIN endpoint e ON tc.endpoint_id = e.id{o("e")}
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


def _test_run_stats(secure: bool) -> str:
    def o(alias: str) -> str:
        return _org(alias, "tr", secure)

    return f"""
CREATE VIEW v_test_run_stats{_with(secure)} AS
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
    COALESCE(u.email, u.name, CAST(u.id AS text)) AS executor_name,
    {_DURATION_MS} AS duration_ms
FROM test_run tr
JOIN status s ON tr.status_id = s.id{o("s")}
LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id{o("tc")}
LEFT JOIN test_set ts ON tc.test_set_id = ts.id{o("ts")} AND ts.deleted_at IS NULL
LEFT JOIN endpoint e ON tc.endpoint_id = e.id{o("e")}
LEFT JOIN "user" u ON tr.user_id = u.id
WHERE tr.deleted_at IS NULL
"""


def _test_stats(secure: bool) -> str:
    def o(alias: str) -> str:
        return _org(alias, "t", secure)

    # Group per (test, organization) so a result can only count toward its own org's test.
    result_org = "\n        trs.organization_id," if secure else ""
    agg_org = "\n        results.organization_id," if secure else ""
    group_org = ", results.organization_id" if secure else ""
    return f"""
CREATE VIEW v_test_stats{_with(secure)} AS
WITH results AS (
    SELECT trs.test_id,{result_org}
        trs.created_at,
        {_RESULT_CASE} AS result
    FROM test_result trs
    WHERE trs.deleted_at IS NULL
), agg AS (
    SELECT results.test_id,{agg_org}
        count(*) AS run_count,
        count(*) FILTER (WHERE results.result = 'passed') AS passed_count,
        count(*) FILTER (WHERE results.result = 'failed') AS failed_count,
        count(*) FILTER (WHERE results.result IN ('pending', 'cancelled')) AS pending_count,
        count(*) FILTER (WHERE results.result = 'error') AS error_count,
        max(results.created_at) AS last_run_at
    FROM results
    GROUP BY results.test_id{group_org}
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
LEFT JOIN agg ON agg.test_id = t.id{o("agg")}
LEFT JOIN requirement r ON t.requirement_id = r.id{o("r")}
LEFT JOIN category c ON t.category_id = c.id{o("c")}
LEFT JOIN topic tp ON t.topic_id = tp.id{o("tp")}
WHERE t.deleted_at IS NULL
"""


def _recreate(secure: bool) -> None:
    for view in _VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {view}")
    for build in (_test_result_stats, _metric_stats, _test_run_stats, _test_stats):
        op.execute(build(secure))


def upgrade() -> None:
    _recreate(secure=True)


def downgrade() -> None:
    _recreate(secure=False)
