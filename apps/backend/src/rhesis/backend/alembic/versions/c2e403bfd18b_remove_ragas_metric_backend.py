"""Remove the Ragas metric backend

Ragas is unmaintained (last release 0.4.3, January 2026) and carries unpatched
advisories, so the provider is gone from the SDK. This drops the four seeded
Ragas metrics, everything that referenced them, and the BackendType row itself.

Requirements linked to a Ragas metric lose that link but survive; any left with
no metrics at all are named in the log rather than deleted.

Metric scores already recorded on test runs are unaffected: ``test_result`` and
``trace`` store them in JSONB keyed by metric name, with no foreign key into
``metric``, so history and the ``v_metric_stats`` view built on it stay intact.

Revision ID: c2e403bfd18b
Revises: cb3558b77459
Create Date: 2026-09-17

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = "c2e403bfd18b"
down_revision: Union[str, None] = "cb3558b77459"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKEND_TYPE_DESCRIPTION = "RAGAS framework for RAG evaluation"

METRICS = """
    SELECT m.id FROM metric m
    JOIN type_lookup tl ON tl.id = m.backend_type_id
    WHERE tl.type_name = 'BackendType' AND tl.type_value = 'ragas'
"""

# Metric tuning owns a private test set and its tests, hidden from the /test_sets
# and /tests lists by a non-NULL metric_id. Clearing the FK would surface them as
# ordinary user content, so they go with the metric. Everything below hangs off
# those two, and is deleted parent-last.
TESTS = f"SELECT id FROM test WHERE metric_id IN ({METRICS})"
TEST_SETS = f"SELECT id FROM test_set WHERE metric_id IN ({METRICS})"
CONFIGS = f"SELECT id FROM test_configuration WHERE test_set_id IN ({TEST_SETS})"
RUNS = f"SELECT id FROM test_run WHERE test_configuration_id IN ({CONFIGS})"

# Comments, tasks and tags reference a metric polymorphically (entity_type/entity_id),
# so no foreign key takes them with it. The mixins write ``type(self).__name__``, hence
# 'Metric'. activity_log is deliberately absent: nothing writes 'Metric' there, and it
# is a hot, growing table whose ACCESS EXCLUSIVE lock is not worth taking for a DELETE
# that can never match.
POLYMORPHIC_TABLES = ("comment", "task", "tagged_item")

# A requirement linked only to Ragas metrics is left evaluating nothing. It is
# user-authored content and recovers by attaching another metric, so it is kept
# rather than deleted -- but it is named in the log so the state isn't silent.
# The seeded 'Reliability' requirement keeps 15 non-Ragas metrics.
ORPHANED_REQUIREMENTS = f"""
    SELECT r.id, r.name, r.organization_id
    FROM requirement r
    JOIN requirement_metric rm ON rm.requirement_id = r.id
    WHERE rm.metric_id IN ({METRICS})
    GROUP BY r.id, r.name, r.organization_id
    HAVING COUNT(*) = (
        SELECT COUNT(*) FROM requirement_metric rm2 WHERE rm2.requirement_id = r.id
    )
"""

# Every table this migration reads or writes. All are ENABLE + FORCE row level
# security at head, so all are restored to both. PROBE_TABLES is the minimum
# needed to answer "did this deployment ever have a Ragas metric?".
PROBE_TABLES = ("metric", "type_lookup")

DATA_TABLES = (
    "test_result",
    "test_run",
    "test_configuration",
    "test_test_set",
    "prompt_test_set",
    "test",
    "test_set",
    "test_set_metric",
    "requirement",
    "requirement_metric",
    "comment",
    "task",
    "tagged_item",
)

RLS_TABLES = PROBE_TABLES + DATA_TABLES

# A test configuration can pin an exact set of metrics by id in attributes['metrics'],
# which execution prefers over the test set's own metrics. Deleting the metric would
# leave a dangling id that re-runs silently skip, so drop the entry instead. Compared
# as text because the snapshot is author-supplied JSON and a non-UUID value there
# would fail the cast.
#
# When nothing is left, 'metrics_source' goes too. Execution treats an empty list as
# falsy and falls back to the test set's or requirement's metrics, so a lingering
# 'execution_time' would claim a pinned set that no longer exists -- which is also
# what the run's configuration tab reads to label the source.
#
# test_run.attributes['metric_plan'] is deliberately left alone: it is the frozen
# record of what a past run actually evaluated, and the verdict grid reads it without
# consulting the metric table.
PRUNE_PINNED_METRICS = f"""
    WITH surviving AS (
        SELECT
            tc.id,
            COALESCE(
                (
                    SELECT jsonb_agg(elem)
                    FROM jsonb_array_elements(tc.attributes -> 'metrics') AS elem
                    WHERE elem ->> 'id' NOT IN (SELECT id::text FROM ({METRICS}) AS ragas)
                ),
                '[]'::jsonb
            ) AS metrics
        FROM test_configuration tc
        WHERE jsonb_typeof(tc.attributes -> 'metrics') = 'array'
          AND EXISTS (
              SELECT 1
              FROM jsonb_array_elements(tc.attributes -> 'metrics') AS elem
              WHERE elem ->> 'id' IN (SELECT id::text FROM ({METRICS}) AS ragas)
          )
    )
    UPDATE test_configuration tc
    SET attributes = CASE
            WHEN jsonb_array_length(s.metrics) = 0
                THEN tc.attributes - 'metrics' - 'metrics_source'
            ELSE jsonb_set(tc.attributes, '{{metrics}}', s.metrics)
        END
    FROM surviving s
    WHERE s.id = tc.id
"""

CLEANUP_STATEMENTS = (
    PRUNE_PINNED_METRICS,
    f"DELETE FROM test_result WHERE test_run_id IN ({RUNS})",
    f"DELETE FROM test_result WHERE test_configuration_id IN ({CONFIGS})",
    f"DELETE FROM test_result WHERE test_id IN ({TESTS})",
    f"DELETE FROM test_run WHERE test_configuration_id IN ({CONFIGS})",
    f"DELETE FROM test_configuration WHERE test_set_id IN ({TEST_SETS})",
    f"DELETE FROM test_test_set WHERE test_id IN ({TESTS})",
    f"DELETE FROM test_test_set WHERE test_set_id IN ({TEST_SETS})",
    f"DELETE FROM prompt_test_set WHERE test_set_id IN ({TEST_SETS})",
    f"DELETE FROM test WHERE metric_id IN ({METRICS})",
    f"DELETE FROM test_set_metric WHERE test_set_id IN ({TEST_SETS})",
    f"DELETE FROM test_set WHERE metric_id IN ({METRICS})",
    f"DELETE FROM test_set_metric WHERE metric_id IN ({METRICS})",
    f"DELETE FROM requirement_metric WHERE metric_id IN ({METRICS})",
    *(
        f"DELETE FROM {table} WHERE entity_type = 'Metric' AND entity_id IN ({METRICS})"
        for table in POLYMORPHIC_TABLES
    ),
    f"DELETE FROM metric WHERE id IN ({METRICS})",
)


def upgrade() -> None:
    # Toggling RLS takes ACCESS EXCLUSIVE on each table, which blocks the live app
    # for as long as the migration runs. Only `metric` and `type_lookup` are needed
    # to find out whether this deployment ever had a Ragas metric; the rest -- which
    # include test_result, the largest table -- stay untouched when it didn't.
    _set_rls(PROBE_TABLES, enabled=False)

    if _has_ragas_metrics():
        _set_rls(DATA_TABLES, enabled=False)
        _warn_about_orphaned_requirements()
        for statement in CLEANUP_STATEMENTS:
            op.execute(f"{statement};")
        _set_rls(DATA_TABLES, enabled=True)

    # Runs either way: the BackendType row is seeded per organization whether or not
    # a metric ever used it.
    op.execute(load_cleanup_type_lookup_template("BackendType", "'ragas'"))

    _set_rls(PROBE_TABLES, enabled=True)


def _set_rls(tables: Sequence[str], *, enabled: bool) -> None:
    """Lift or restore row level security.

    Every table here is FORCE ROW LEVEL SECURITY with a strict ``tenant_isolation``
    policy on ``current_setting('app.current_organization')`` and no missing_ok
    argument. A migration binds no organization, so with RLS left on the statement
    raises ``unrecognized configuration parameter`` instead of deleting -- and this
    removal is org-wide by definition. DDL is transactional in PostgreSQL, so a
    failure rolls the disable back along with everything else.
    """
    for table in tables:
        if enabled:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        else:
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def _has_ragas_metrics() -> bool:
    return bool(op.get_bind().execute(sa.text(f"SELECT 1 FROM ({METRICS}) m LIMIT 1")).fetchone())


def _warn_about_orphaned_requirements() -> None:
    """Name requirements that will be left with no metrics at all."""
    orphaned = op.get_bind().execute(sa.text(ORPHANED_REQUIREMENTS)).fetchall()
    for requirement_id, name, organization_id in orphaned:
        logger.warning(
            "Requirement %r (%s, org %s) was linked only to Ragas metrics and now "
            "has none; attach another metric for it to be evaluated again.",
            name,
            requirement_id,
            organization_id,
        )


def downgrade() -> None:
    # Only the backend type comes back. The metrics themselves are seed data,
    # reinstated by onboarding rather than here. The template fans the row out to
    # every organization, so it needs the same RLS treatment as upgrade().
    op.execute("ALTER TABLE type_lookup DISABLE ROW LEVEL SECURITY;")
    op.execute(load_type_lookup_template(f"('BackendType', 'ragas', '{BACKEND_TYPE_DESCRIPTION}')"))
    op.execute("ALTER TABLE type_lookup ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE type_lookup FORCE ROW LEVEL SECURITY;")
