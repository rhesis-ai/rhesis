"""Add the requirement's impact and parent to the stats views

v_test_result_stats, v_metric_stats and v_test_stats gain impact_id and
impact_name (requirement -> type_lookup) plus requirement_parent_id and
requirement_parent_name (requirement -> its parent requirement), so Insights
can group and filter by them. A requirement without an impact or parent keeps
NULLs in those columns and still counts.

The definitions are otherwise those of c47fd570587b. The new columns are
appended, so the upgrade replaces each view in place and keeps its grants; the
downgrade has to drop and recreate to remove them, and re-issues the grants it
found.

Revision ID: f1a7c3e9d2b5
Revises: 227d4f9c1e29
Create Date: 2026-11-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a7c3e9d2b5"
down_revision: Union[str, None] = "227d4f9c1e29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VIEWS = ("v_test_result_stats", "v_metric_stats", "v_test_stats")
_WITH = " WITH (security_invoker = true)"

_RESULT_CASE = """CASE
        WHEN trs.execution = 'ok' AND trs.verdict = 'pass' THEN 'passed'
        WHEN trs.execution = 'ok' AND trs.verdict = 'fail' THEN 'failed'
        WHEN trs.execution = 'error' THEN 'error'
        WHEN trs.execution = 'cancelled' THEN 'cancelled'
        ELSE 'pending'
    END"""


def _org(alias: str, anchor: str) -> str:
    return f" AND {alias}.organization_id = {anchor}.organization_id"


def _requirement_columns(rich: bool, indent: str = "    ") -> str:
    if not rich:
        return ""
    return (
        f",\n{indent}r.impact_id,"
        f"\n{indent}imp.type_value AS impact_name,"
        f"\n{indent}r.parent_id AS requirement_parent_id,"
        f"\n{indent}rp.name AS requirement_parent_name"
    )


def _requirement_joins(rich: bool, anchor: str, indent: str = "") -> str:
    if not rich:
        return ""
    return (
        f"\n{indent}LEFT JOIN type_lookup imp ON r.impact_id = imp.id{_org('imp', anchor)}"
        f"\n{indent}LEFT JOIN requirement rp ON r.parent_id = rp.id{_org('rp', anchor)}"
    )


def _test_result_stats(rich: bool, create: str = "CREATE OR REPLACE VIEW") -> str:
    def o(alias: str) -> str:
        return _org(alias, "trs")

    return f"""
{create} v_test_result_stats{_WITH} AS
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
    COALESCE(u.email, u.name, CAST(u.id AS text)) AS executor_name{_requirement_columns(rich)}
FROM test_result trs
JOIN test t ON trs.test_id = t.id{o("t")} AND t.deleted_at IS NULL
JOIN status s ON trs.status_id = s.id{o("s")}
LEFT JOIN requirement r ON t.requirement_id = r.id{o("r")}{_requirement_joins(rich, "trs")}
LEFT JOIN category c ON t.category_id = c.id{o("c")}
LEFT JOIN topic tp ON t.topic_id = tp.id{o("tp")}
LEFT JOIN test_run tr ON trs.test_run_id = tr.id{o("tr")}
LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id{o("tc")}
LEFT JOIN test_set ts ON tc.test_set_id = ts.id{o("ts")} AND ts.deleted_at IS NULL
LEFT JOIN endpoint e ON tc.endpoint_id = e.id{o("e")}
LEFT JOIN "user" u ON tr.user_id = u.id
WHERE trs.deleted_at IS NULL
"""


def _metric_stats(rich: bool, create: str = "CREATE OR REPLACE VIEW") -> str:
    def o(alias: str) -> str:
        return _org(alias, "trs")

    outer = (
        ",\n    impact_id,\n    impact_name,\n    requirement_parent_id,\n    requirement_parent_name"
        if rich
        else ""
    )
    return f"""
{create} v_metric_stats{_WITH} AS
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
        END AS score{_requirement_columns(rich, indent="        ")}
    FROM test_result trs
    JOIN test t ON trs.test_id = t.id{o("t")} AND t.deleted_at IS NULL
    LEFT JOIN requirement r ON t.requirement_id = r.id{o("r")}{_requirement_joins(rich, "trs", "    ")}
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
    score{outer}
FROM unnested
"""


def _test_stats(rich: bool, create: str = "CREATE OR REPLACE VIEW") -> str:
    def o(alias: str) -> str:
        return _org(alias, "t")

    return f"""
{create} v_test_stats{_WITH} AS
WITH results AS (
    SELECT trs.test_id,
        trs.organization_id,
        trs.created_at,
        {_RESULT_CASE} AS result
    FROM test_result trs
    WHERE trs.deleted_at IS NULL
), agg AS (
    SELECT results.test_id,
        results.organization_id,
        count(*) AS run_count,
        count(*) FILTER (WHERE results.result = 'passed') AS passed_count,
        count(*) FILTER (WHERE results.result = 'failed') AS failed_count,
        count(*) FILTER (WHERE results.result IN ('pending', 'cancelled')) AS pending_count,
        count(*) FILTER (WHERE results.result = 'error') AS error_count,
        max(results.created_at) AS last_run_at
    FROM results
    GROUP BY results.test_id, results.organization_id
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
    COALESCE(agg.error_count, 0) AS error_count{_requirement_columns(rich)}
FROM test t
LEFT JOIN agg ON agg.test_id = t.id{o("agg")}
LEFT JOIN requirement r ON t.requirement_id = r.id{o("r")}{_requirement_joins(rich, "t")}
LEFT JOIN category c ON t.category_id = c.id{o("c")}
LEFT JOIN topic tp ON t.topic_id = tp.id{o("tp")}
WHERE t.deleted_at IS NULL
"""


_BUILDERS = (_test_result_stats, _metric_stats, _test_stats)


def _select_grantees(view: str) -> list:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT grantee FROM information_schema.role_table_grants"
            " WHERE table_schema = 'public' AND table_name = :view"
            " AND privilege_type = 'SELECT' AND grantee <> CURRENT_USER"
        ),
        {"view": view},
    )
    return [row[0] for row in rows]


# Appending columns is allowed in a replace, which keeps the existing grants.
def upgrade() -> None:
    for build in _BUILDERS:
        op.execute(build(rich=True))


# Removing columns is not, so drop and recreate, then give back the SELECTs.
def downgrade() -> None:
    for view, build in zip(_VIEWS, _BUILDERS, strict=True):
        grantees = _select_grantees(view)
        op.execute(f"DROP VIEW {view}")
        op.execute(build(rich=False, create="CREATE VIEW"))
        for grantee in grantees:
            target = "PUBLIC" if grantee == "PUBLIC" else f'"{grantee}"'
            op.execute(f"GRANT SELECT ON {view} TO {target}")
