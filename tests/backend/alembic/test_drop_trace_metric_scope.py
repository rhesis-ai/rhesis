"""Data-level checks for the migration that drops the Trace metric scope.

Drives the migration's ``upgrade()`` against the ``admin_test_db`` connection
inside an ``Operations.context``, so everything rolls back at teardown. The
schema is already at head; these tests re-run the migration on rows seeded here.
"""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

RHESIS_SKIP_MIGRATIONS = os.environ.get("RHESIS_SKIP_MIGRATIONS", "").lower() in (
    "1",
    "true",
    "yes",
)

pytestmark = pytest.mark.skipif(
    RHESIS_SKIP_MIGRATIONS,
    reason="Depends on the head schema; skipped when RHESIS_SKIP_MIGRATIONS is set.",
)

_MIGRATION_PATH = (
    Path(__file__).parents[3]
    / "apps/backend/src/rhesis/backend/alembic/versions"
    / "7c3e9a1b5d20_drop_trace_metric_scope.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "drop_trace_metric_scope_under_test", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()


@pytest.fixture
def conn(admin_test_db):
    return admin_test_db.connection()


@pytest.fixture
def migration_ops(admin_test_db):
    """Activates an Operations context so the migration's bare ``op.xxx`` calls resolve."""
    ctx = MigrationContext.configure(admin_test_db.connection())
    with Operations.context(ctx):
        yield


@pytest.fixture
def make_metric(conn, test_org_id, authenticated_user_id):
    def _make(scope: str):
        return conn.execute(
            sa.text(
                """
                INSERT INTO metric (name, evaluation_prompt, score_type, metric_scope,
                                    organization_id, user_id)
                VALUES (:name, 'prompt', 'numeric', CAST(:scope AS jsonb),
                        CAST(:org AS uuid), CAST(:usr AS uuid))
                RETURNING id
                """
            ),
            {
                "name": f"scope {uuid.uuid4().hex[:8]}",
                "scope": scope,
                "org": test_org_id,
                "usr": authenticated_user_id,
            },
        ).scalar()

    return _make


def _scope(conn, metric_id):
    return conn.execute(
        sa.text("SELECT metric_scope FROM metric WHERE id = :id"), {"id": metric_id}
    ).scalar()


@pytest.mark.unit
class TestDropTraceMetricScope:
    def test_strips_trace_and_keeps_the_rest(self, conn, make_metric, migration_ops):
        mixed = make_metric('["Trace", "Single-Turn"]')
        universal = make_metric('["Single-Turn", "Multi-Turn", "Trace"]')
        untouched = make_metric('["Single-Turn"]')

        _migration.upgrade()

        assert _scope(conn, mixed) == ["Single-Turn"]
        assert _scope(conn, universal) == ["Single-Turn", "Multi-Turn"]
        assert _scope(conn, untouched) == ["Single-Turn"]

    def test_trace_only_becomes_both_scopes(self, conn, make_metric, migration_ops):
        trace_only = make_metric('["Trace"]')

        _migration.upgrade()

        assert _scope(conn, trace_only) == ["Single-Turn", "Multi-Turn"]

    def test_removes_the_lookup_row(self, conn, test_org_id, migration_ops):
        conn.execute(
            sa.text(
                """
                INSERT INTO type_lookup (type_name, type_value, description, organization_id)
                VALUES ('MetricScope', 'Trace', 'seeded by test', CAST(:org AS uuid))
                """
            ),
            {"org": test_org_id},
        )

        _migration.upgrade()

        remaining = conn.execute(
            sa.text(
                "SELECT count(*) FROM type_lookup "
                "WHERE type_name = 'MetricScope' AND type_value = 'Trace'"
            )
        ).scalar()
        assert remaining == 0
