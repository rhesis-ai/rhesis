"""Data-level checks for the migration that replaces metric_scope with a target.

The schema is at head, where the column is gone, so each test adds it back inside the
``admin_test_db`` transaction, seeds rows, and runs ``upgrade()``. Everything rolls back
at teardown.
"""

import importlib.util
import json
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

pytestmark = pytest.mark.skipif(
    os.environ.get("RHESIS_SKIP_MIGRATIONS", "").lower() in ("1", "true", "yes"),
    reason="Depends on the head schema; skipped when RHESIS_SKIP_MIGRATIONS is set.",
)

_MIGRATION_PATH = (
    Path(__file__).parents[3]
    / "apps/backend/src/rhesis/backend/alembic/versions"
    / "a7c4e2f9b318_replace_metric_scope_with_target.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "replace_metric_scope_under_test", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()


@pytest.fixture
def conn(admin_test_db):
    connection = admin_test_db.connection()
    # The column and its CHECK as they were before this revision.
    connection.execute(sa.text("ALTER TABLE metric ADD COLUMN metric_scope jsonb"))
    connection.execute(
        sa.text(
            "ALTER TABLE metric ADD CONSTRAINT ck_metric_metric_scope_non_empty CHECK "
            "(metric_scope IS NULL OR jsonb_typeof(metric_scope) = 'array')"
        )
    )
    return connection


@pytest.fixture
def migration_ops(conn):
    with Operations.context(MigrationContext.configure(conn)):
        yield


@pytest.fixture
def make_metric(conn, test_org_id, authenticated_user_id):
    def _make(scope, class_name="NumericJudge", config=None, examples=None, reference=False):
        return conn.execute(
            sa.text(
                """
                INSERT INTO metric (name, evaluation_prompt, score_type, metric_scope, class_name,
                                    config, evaluation_examples, ground_truth_required,
                                    organization_id, user_id)
                VALUES (:name, 'prompt', 'numeric', CAST(:scope AS jsonb), :class_name,
                        CAST(:config AS jsonb), :examples, :reference,
                        CAST(:org AS uuid), CAST(:usr AS uuid))
                RETURNING id
                """
            ),
            {
                "name": f"metric {uuid.uuid4().hex[:8]}",
                "scope": json.dumps(scope),
                "class_name": class_name,
                "config": json.dumps(config) if config is not None else None,
                "examples": examples,
                "reference": reference,
                "org": test_org_id,
                "usr": authenticated_user_id,
            },
        ).scalar()

    return _make


def _config(conn, metric_id):
    return conn.execute(
        sa.text("SELECT config FROM metric WHERE id = :id"), {"id": metric_id}
    ).scalar()


def _reference(conn, metric_id):
    return conn.execute(
        sa.text("SELECT ground_truth_required FROM metric WHERE id = :id"), {"id": metric_id}
    ).scalar()


def _sdk(*accepted):
    return json.dumps({"sdk_connection": {"accepted_params": list(accepted)}})


@pytest.mark.unit
class TestReplaceMetricScopeWithTarget:
    def test_each_scope_becomes_a_target(self, conn, make_metric, migration_ops):
        single = make_metric(["Single-Turn"])
        both = make_metric(["Single-Turn", "Multi-Turn"])
        multi = make_metric(["Multi-Turn"])
        conversational = make_metric(["Single-Turn", "Multi-Turn"], "ConversationalJudge")
        trajectory = make_metric(["Single-Turn", "Multi-Turn"], "ToolCallTrajectory")

        _migration.upgrade()

        assert _config(conn, single) == {"target": {"on": "turn"}}
        assert _config(conn, both) == {"target": {"on": "run"}}
        assert _config(conn, multi) == {"target": {"on": "conversation"}}
        assert _config(conn, conversational) == {"target": {"on": "conversation"}}
        assert _config(conn, trajectory) == {"target": {"on": "run"}}

    @pytest.mark.parametrize("scope", [["Multi-Turn"], ["Single-Turn", "Multi-Turn"]])
    def test_a_class_that_cant_read_the_whole_trace_judges_each_turn(
        self, conn, make_metric, migration_ops, scope
    ):
        toxicity = make_metric(scope, "DeepEvalToxicity")
        io_only = make_metric(scope, "my_check", examples=_sdk("input", "output"))

        _migration.upgrade()

        assert _config(conn, toxicity) == {"target": {"on": "turn"}}
        assert _config(conn, io_only) == {"target": {"on": "turn"}}

    def test_a_conversation_metric_no_longer_requires_a_reference_answer(
        self, conn, make_metric, migration_ops
    ):
        multi = make_metric(["Multi-Turn"], reference=True)
        single = make_metric(["Single-Turn"], reference=True)
        recall = make_metric(["Multi-Turn"], "DeepEvalContextualRecall", reference=True)

        _migration.upgrade()

        assert _config(conn, multi) == {"target": {"on": "conversation"}}
        assert _reference(conn, multi) is False
        assert _reference(conn, single) is True
        assert _config(conn, recall) == {"target": {"on": "turn"}}
        assert _reference(conn, recall) is True

    def test_a_code_metric_reading_only_the_trace_judges_the_run(
        self, conn, make_metric, migration_ops
    ):
        trace_only = make_metric(["Single-Turn"], "my_check", examples=_sdk("trace"))

        _migration.upgrade()

        assert _config(conn, trace_only) == {"target": {"on": "run"}}

    def test_settings_and_a_chosen_target_are_kept(self, conn, make_metric, migration_ops):
        settings = make_metric(["Single-Turn"], "ToolCallTrajectory", config={"match": "exact"})
        chosen = make_metric(["Single-Turn"], config={"target": {"on": "retrieval"}})

        _migration.upgrade()

        assert _config(conn, settings) == {"match": "exact", "target": {"on": "run"}}
        assert _config(conn, chosen) == {"target": {"on": "retrieval"}}

    def test_the_downgrade_gives_every_target_but_the_conversation_both_scopes(
        self, conn, make_metric, migration_ops
    ):
        single = make_metric(["Single-Turn"])
        multi = make_metric(["Multi-Turn"])

        _migration.upgrade()
        _migration.downgrade()

        scope = sa.text("SELECT metric_scope FROM metric WHERE id = :id")
        assert conn.execute(scope, {"id": single}).scalar() == ["Single-Turn", "Multi-Turn"]
        assert conn.execute(scope, {"id": multi}).scalar() == ["Multi-Turn"]

    def test_the_column_and_the_lookups_go(self, conn, test_org_id, migration_ops):
        conn.execute(
            sa.text(
                """
                INSERT INTO type_lookup (type_name, type_value, description, organization_id)
                VALUES ('MetricScope', 'Single-Turn', 'seeded by test', CAST(:org AS uuid))
                """
            ),
            {"org": test_org_id},
        )

        _migration.upgrade()

        columns = {c["name"] for c in sa.inspect(conn).get_columns("metric")}
        assert "metric_scope" not in columns
        lookups = conn.execute(
            sa.text("SELECT count(*) FROM type_lookup WHERE type_name = 'MetricScope'")
        ).scalar()
        assert lookups == 0
