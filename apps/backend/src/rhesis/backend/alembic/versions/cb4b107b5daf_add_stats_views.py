from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cb4b107b5daf"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

V_TEST_RUN_STATS = """
CREATE OR REPLACE VIEW v_test_run_stats AS
SELECT
    tr.id            AS test_run_id,
    tr.organization_id,
    tr.created_at,
    tr.user_id,
    s.name           AS status_name,
    CASE
        WHEN s.name ILIKE '%%complet%%' THEN 'passed'
        WHEN s.name ILIKE '%%fail%%'    THEN 'failed'
        ELSE 'pending'
    END              AS result,
    tc.test_set_id,
    tc.endpoint_id,
    ts.name          AS test_set_name,
    COALESCE(u.email, u.name, u.id::text) AS executor_name,
    EXTRACT(YEAR  FROM tr.created_at)::int AS year,
    EXTRACT(MONTH FROM tr.created_at)::int AS month
FROM test_run tr
JOIN status s ON tr.status_id = s.id
LEFT JOIN test_configuration tc ON tr.test_configuration_id = tc.id
LEFT JOIN test_set ts ON tc.test_set_id = ts.id AND ts.deleted_at IS NULL
LEFT JOIN "user" u ON tr.user_id = u.id
WHERE tr.deleted_at IS NULL
"""

V_TEST_RESULT_STATS = """
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
        WHEN s.name ILIKE ANY(ARRAY['%%pass%%','%%success%%','%%complet%%'])
            THEN 'passed'
        WHEN s.name ILIKE ANY(ARRAY['%%fail%%','%%error%%'])
            THEN 'failed'
        ELSE 'pending'
    END              AS result,
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
    EXTRACT(YEAR  FROM trs.created_at)::int AS year,
    EXTRACT(MONTH FROM trs.created_at)::int AS month
FROM test_result trs
JOIN test t    ON trs.test_id   = t.id
JOIN status s  ON trs.status_id = s.id
LEFT JOIN behavior b  ON t.behavior_id = b.id
LEFT JOIN category c  ON t.category_id = c.id
LEFT JOIN topic tp    ON t.topic_id    = tp.id
LEFT JOIN test_run tr ON trs.test_run_id = tr.id
WHERE trs.deleted_at IS NULL
"""


def upgrade() -> None:
    op.execute(V_TEST_RUN_STATS)
    op.execute(V_TEST_RESULT_STATS)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_test_result_stats")
    op.execute("DROP VIEW IF EXISTS v_test_run_stats")
