"""Derive v_test_result_stats/v_test_stats.result from execution/verdict

ff71b040aebf added test_result.execution/verdict as the source of truth for
pass/fail/error, but both stats views still derived their `result` column
from a status-name CASE with a synonym list -- and that CASE had no branch
for Error or Cancelled, so both silently read as `pending`. See
playground/outcome-model/phase-4-5-in-pr2.md for the read-path migration
this is part of.

v_test_result_stats: same columns, `result` now distinguishes error and
cancelled from pending. status_name/result_status_id are unchanged --
insights' status-dimension filter still needs them.

v_test_stats: same CASE, plus a new trailing `error_count` column. Rows
that were previously bucketed into pending_count because their status was
Error now count separately; cancelled still folds into pending_count via
the aggregate FILTER, since the view has no cancelled_count column.

Revision ID: 84d6c1464b96
Revises: c7e2f4a91b83
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op

revision: str = "84d6c1464b96"
down_revision: Union[str, None] = "c7e2f4a91b83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RESULT_CASE = """CASE
        WHEN trs.execution = 'ok' AND trs.verdict = 'pass' THEN 'passed'
        WHEN trs.execution = 'ok' AND trs.verdict = 'fail' THEN 'failed'
        WHEN trs.execution = 'error' THEN 'error'
        WHEN trs.execution = 'cancelled' THEN 'cancelled'
        ELSE 'pending'
    END"""

V_TEST_RESULT_STATS_UP = f"""
CREATE OR REPLACE VIEW v_test_result_stats AS
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
    EXTRACT(year FROM (trs.created_at AT TIME ZONE 'UTC'))::integer AS year,
    EXTRACT(month FROM (trs.created_at AT TIME ZONE 'UTC'))::integer AS month
FROM test_result trs
JOIN test t ON trs.test_id = t.id AND t.deleted_at IS NULL
JOIN status s ON trs.status_id = s.id
LEFT JOIN requirement r ON t.requirement_id = r.id
LEFT JOIN category c ON t.category_id = c.id
LEFT JOIN topic tp ON t.topic_id = tp.id
LEFT JOIN test_run tr ON trs.test_run_id = tr.id
WHERE trs.deleted_at IS NULL
"""

V_TEST_RESULT_STATS_DOWN = """
CREATE OR REPLACE VIEW v_test_result_stats AS
SELECT trs.id AS test_result_id,
    trs.organization_id,
    trs.created_at,
    trs.test_run_id,
    trs.test_id,
    trs.test_metrics,
    s.name AS status_name,
    CASE
        WHEN lower(s.name) = ANY (ARRAY['complete', 'completed', 'done', 'finished', 'pass', 'passed', 'success', 'successful']) THEN 'passed'
        WHEN lower(s.name) = ANY (ARRAY['fail', 'failed']) THEN 'failed'
        ELSE 'pending'
    END AS result,
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
    EXTRACT(year FROM (trs.created_at AT TIME ZONE 'UTC'))::integer AS year,
    EXTRACT(month FROM (trs.created_at AT TIME ZONE 'UTC'))::integer AS month
FROM test_result trs
JOIN test t ON trs.test_id = t.id AND t.deleted_at IS NULL
JOIN status s ON trs.status_id = s.id
LEFT JOIN requirement r ON t.requirement_id = r.id
LEFT JOIN category c ON t.category_id = c.id
LEFT JOIN topic tp ON t.topic_id = tp.id
LEFT JOIN test_run tr ON trs.test_run_id = tr.id
WHERE trs.deleted_at IS NULL
"""

V_TEST_STATS_UP = f"""
CREATE OR REPLACE VIEW v_test_stats AS
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
    EXTRACT(year FROM t.created_at)::integer AS year,
    EXTRACT(month FROM t.created_at)::integer AS month,
    COALESCE(agg.run_count, 0::bigint) AS run_count,
    COALESCE(agg.passed_count, 0::bigint) AS passed_count,
    COALESCE(agg.failed_count, 0::bigint) AS failed_count,
    COALESCE(agg.pending_count, 0::bigint) AS pending_count,
    agg.run_count IS NULL OR agg.run_count = 0 AS is_unrun,
    agg.last_run_at,
    COALESCE(agg.error_count, 0::bigint) AS error_count
FROM test t
LEFT JOIN agg ON agg.test_id = t.id
LEFT JOIN requirement r ON t.requirement_id = r.id
LEFT JOIN category c ON t.category_id = c.id
LEFT JOIN topic tp ON t.topic_id = tp.id
WHERE t.deleted_at IS NULL
"""

V_TEST_STATS_DOWN = """
CREATE VIEW v_test_stats AS
WITH results AS (
    SELECT trs.test_id,
        trs.created_at,
        CASE
            WHEN lower(s.name) = ANY (ARRAY['complete', 'completed', 'done', 'finished', 'pass', 'passed', 'success', 'successful']) THEN 'passed'
            WHEN lower(s.name) = ANY (ARRAY['fail', 'failed']) THEN 'failed'
            ELSE 'pending'
        END AS result
    FROM test_result trs
    JOIN status s ON trs.status_id = s.id
    WHERE trs.deleted_at IS NULL
), agg AS (
    SELECT results.test_id,
        count(*) AS run_count,
        count(*) FILTER (WHERE results.result = 'passed') AS passed_count,
        count(*) FILTER (WHERE results.result = 'failed') AS failed_count,
        count(*) FILTER (WHERE results.result = 'pending') AS pending_count,
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
    EXTRACT(year FROM t.created_at)::integer AS year,
    EXTRACT(month FROM t.created_at)::integer AS month,
    COALESCE(agg.run_count, 0::bigint) AS run_count,
    COALESCE(agg.passed_count, 0::bigint) AS passed_count,
    COALESCE(agg.failed_count, 0::bigint) AS failed_count,
    COALESCE(agg.pending_count, 0::bigint) AS pending_count,
    agg.run_count IS NULL OR agg.run_count = 0 AS is_unrun,
    agg.last_run_at
FROM test t
LEFT JOIN agg ON agg.test_id = t.id
LEFT JOIN requirement r ON t.requirement_id = r.id
LEFT JOIN category c ON t.category_id = c.id
LEFT JOIN topic tp ON t.topic_id = tp.id
WHERE t.deleted_at IS NULL
"""


def upgrade() -> None:
    op.execute(V_TEST_RESULT_STATS_UP)
    op.execute(V_TEST_STATS_UP)


def downgrade() -> None:
    op.execute(V_TEST_RESULT_STATS_DOWN)
    # error_count is a trailing column CREATE OR REPLACE added; removing it
    # needs a real drop, not a replace.
    op.execute("DROP VIEW IF EXISTS v_test_stats")
    op.execute(V_TEST_STATS_DOWN)
