"""Data-level checks for the migration that adds rules.

The schema is at head, so each test runs ``upgrade()`` or ``downgrade()`` inside the
``admin_test_db`` transaction, with the metric sync's session kept in that transaction too.
Everything rolls back at teardown.
"""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    os.environ.get("RHESIS_SKIP_MIGRATIONS", "").lower() in ("1", "true", "yes"),
    reason="Depends on the head schema; skipped when RHESIS_SKIP_MIGRATIONS is set.",
)

_MIGRATION_PATH = (
    Path(__file__).parents[3]
    / "apps/backend/src/rhesis/backend/alembic/versions"
    / "b6f1d3a8c9e2_add_rule_metrics.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("add_rule_metrics_under_test", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()


@pytest.fixture
def conn(admin_test_db):
    return admin_test_db.connection()


@pytest.fixture
def migration_ops(conn, monkeypatch):
    def sync_in_test_transaction(callback):
        # The sync would commit its own session; here it writes into the test's transaction.
        session = Session(bind=conn)
        callback(session)
        session.flush()

    monkeypatch.setattr(_migration, "_sync", sync_in_test_transaction)
    with Operations.context(MigrationContext.configure(conn)):
        yield


def _type_id(conn, org_id, value):
    found = conn.execute(
        sa.text(
            "SELECT id FROM type_lookup WHERE type_name = 'MetricType' AND type_value = :v "
            "AND organization_id = CAST(:org AS uuid) LIMIT 1"
        ),
        {"v": value, "org": org_id},
    ).scalar()
    if found is not None:
        return found
    return conn.execute(
        sa.text(
            "INSERT INTO type_lookup (type_name, type_value, organization_id) "
            "VALUES ('MetricType', :v, CAST(:org AS uuid)) RETURNING id"
        ),
        {"v": value, "org": org_id},
    ).scalar()


def _metric_type(conn, metric_id):
    return conn.execute(
        sa.text(
            "SELECT t.type_value FROM metric m JOIN type_lookup t ON t.id = m.metric_type_id "
            "WHERE m.id = :id"
        ),
        {"id": metric_id},
    ).scalar()


def _metric_types_by_name(conn, org_id, names):
    rows = conn.execute(
        sa.text(
            "SELECT m.name, t.type_value FROM metric m "
            "LEFT JOIN type_lookup t ON t.id = m.metric_type_id "
            "WHERE m.organization_id = CAST(:org AS uuid) AND m.name = ANY(:names)"
        ),
        {"org": org_id, "names": list(names)},
    ).all()
    return dict(rows)


@pytest.fixture
def trajectory(conn, test_org_id, authenticated_user_id):
    return conn.execute(
        sa.text(
            """
            INSERT INTO metric (name, evaluation_prompt, score_type, class_name, config,
                                metric_type_id, organization_id, user_id)
            VALUES (:name, 'Compare.', 'numeric', 'ToolCallTrajectory',
                    CAST(:config AS jsonb), CAST(:type_id AS uuid),
                    CAST(:org AS uuid), CAST(:usr AS uuid))
            RETURNING id
            """
        ),
        {
            "name": f"trajectory {uuid.uuid4().hex[:8]}",
            "config": '{"match": "in_order", "target": {"on": "run"}}',
            "type_id": str(_type_id(conn, test_org_id, "custom-code")),
            "org": test_org_id,
            "usr": authenticated_user_id,
        },
    ).scalar()


@pytest.mark.unit
class TestAddRuleMetrics:
    def test_tool_call_trajectory_becomes_a_rule(self, conn, trajectory, migration_ops):
        _migration.upgrade()

        assert _metric_type(conn, trajectory) == "rule"

    def test_every_organization_gets_the_presets_as_rules(self, conn, test_org_id, migration_ops):
        _migration.upgrade()

        types = _metric_types_by_name(conn, test_org_id, _migration.PRESET_NAMES)
        assert types == {name: "rule" for name in _migration.PRESET_NAMES}

    def test_the_rule_type_is_described(self, conn, test_org_id, migration_ops):
        _migration.upgrade()

        description = conn.execute(
            sa.text(
                "SELECT description FROM type_lookup WHERE type_name = 'MetricType' "
                "AND type_value = 'rule' AND organization_id = CAST(:org AS uuid)"
            ),
            {"org": test_org_id},
        ).scalar()
        assert description == _migration.RULE_DESCRIPTION

    def test_running_it_twice_changes_nothing(self, conn, test_org_id, migration_ops):
        _migration.upgrade()
        _migration.upgrade()

        count = conn.execute(
            sa.text(
                "SELECT count(*) FROM type_lookup WHERE type_name = 'MetricType' "
                "AND type_value = 'rule' AND organization_id = CAST(:org AS uuid)"
            ),
            {"org": test_org_id},
        ).scalar()
        assert count == 1
        types = _metric_types_by_name(conn, test_org_id, _migration.PRESET_NAMES)
        assert len(types) == len(_migration.PRESET_NAMES)

    def test_the_downgrade_moves_rules_back_to_code(
        self, conn, test_org_id, trajectory, migration_ops
    ):
        _migration.upgrade()
        _migration.downgrade()

        assert _metric_type(conn, trajectory) == "custom-code"
        assert _metric_types_by_name(conn, test_org_id, _migration.PRESET_NAMES) == {}

    def test_the_downgrade_keeps_an_organizations_own_metric_named_like_a_preset(
        self, conn, test_org_id, authenticated_user_id, migration_ops
    ):
        own = conn.execute(
            sa.text(
                """
                INSERT INTO metric (name, evaluation_prompt, score_type, class_name,
                                    organization_id, user_id)
                VALUES ('Response Time', 'Was it quick?', 'numeric', 'NumericJudge',
                        CAST(:org AS uuid), CAST(:usr AS uuid))
                RETURNING id
                """
            ),
            {"org": test_org_id, "usr": authenticated_user_id},
        ).scalar()

        _migration.upgrade()
        _migration.downgrade()

        kept = conn.execute(sa.text("SELECT count(*) FROM metric WHERE id = :id"), {"id": own})
        assert kept.scalar() == 1
