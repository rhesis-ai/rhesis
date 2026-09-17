"""Data-level checks for the Ragas removal migration.

Drives the migration's ``upgrade()`` directly against the ``test_db`` connection
inside an ``Operations.context``, so everything rolls back at teardown. The
migration has already run once to bring the schema to head; these tests re-run it
against rows seeded here, which is what exercises the real SQL.

Two cases carry the weight. A requirement linked to a Ragas metric must lose the
link but survive -- it is user-authored and recovers by attaching another metric.
And a test configuration that pinned a Ragas metric by id must not be left holding
a dangling reference.
"""

import importlib.util
import json
import os
import re
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
    / "c2e403bfd18b_remove_ragas_metric_backend.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "remove_ragas_migration_under_test", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()


def _scalar(conn, sql: str, **params):
    return conn.execute(sa.text(sql), params).scalar()


def _backend_type_id(conn, value: str):
    return _scalar(
        conn,
        "SELECT id FROM type_lookup WHERE type_name = 'BackendType' AND type_value = :v",
        v=value,
    )


@pytest.fixture
def conn(test_db):
    return test_db.connection()


@pytest.fixture
def migration_ops(test_db):
    """Activates an Operations context so the migration's bare ``op.xxx`` calls resolve."""
    ctx = MigrationContext.configure(test_db.connection())
    with Operations.context(ctx):
        yield


@pytest.fixture
def backend_type(conn, test_org_id, authenticated_user_id):
    """Resolve a BackendType by value, seeding it when the migration already removed it."""

    def _resolve(value: str):
        existing = _backend_type_id(conn, value)
        if existing is not None:
            return existing
        return _scalar(
            conn,
            """
            INSERT INTO type_lookup (type_name, type_value, description,
                                     organization_id, user_id)
            VALUES ('BackendType', :v, 'seeded by test',
                    CAST(:org AS uuid), CAST(:usr AS uuid))
            RETURNING id
            """,
            v=value,
            org=test_org_id,
            usr=authenticated_user_id,
        )

    return _resolve


@pytest.fixture
def make_metric(conn, test_org_id, authenticated_user_id):
    def _make(backend_type_id, label: str):
        return _scalar(
            conn,
            """
            INSERT INTO metric (name, evaluation_prompt, score_type, metric_scope,
                                backend_type_id, organization_id, user_id)
            VALUES (:name, 'prompt', 'numeric', CAST('["Single-Turn"]' AS jsonb),
                    CAST(:backend AS uuid), CAST(:org AS uuid), CAST(:usr AS uuid))
            RETURNING id
            """,
            name=f"{label} {uuid.uuid4().hex[:8]}",
            backend=backend_type_id,
            org=test_org_id,
            usr=authenticated_user_id,
        )

    return _make


@pytest.fixture
def make_requirement(conn, test_org_id, authenticated_user_id):
    def _make(*metric_ids):
        requirement = _scalar(
            conn,
            """
            INSERT INTO requirement (name, organization_id, user_id)
            VALUES (:name, CAST(:org AS uuid), CAST(:usr AS uuid))
            RETURNING id
            """,
            name=f"req {uuid.uuid4().hex[:8]}",
            org=test_org_id,
            usr=authenticated_user_id,
        )
        for metric_id in metric_ids:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO requirement_metric (requirement_id, metric_id,
                                                    organization_id, user_id)
                    VALUES (CAST(:req AS uuid), CAST(:metric AS uuid),
                            CAST(:org AS uuid), CAST(:usr AS uuid))
                    """
                ),
                {
                    "req": requirement,
                    "metric": metric_id,
                    "org": test_org_id,
                    "usr": authenticated_user_id,
                },
            )
        return requirement

    return _make


@pytest.fixture
def make_test_configuration(conn, db_endpoint, test_org_id, authenticated_user_id):
    def _make(*metric_ids):
        pinned = json.dumps(
            {
                "metrics": [{"id": str(m), "name": f"pinned {m}"} for m in metric_ids],
                "metrics_source": "execution_time",
            }
        )
        return _scalar(
            conn,
            """
            INSERT INTO test_configuration (endpoint_id, organization_id, user_id, attributes)
            VALUES (CAST(:endpoint AS uuid), CAST(:org AS uuid), CAST(:usr AS uuid),
                    CAST(:attrs AS jsonb))
            RETURNING id
            """,
            endpoint=str(db_endpoint.id),
            org=test_org_id,
            usr=authenticated_user_id,
            attrs=pinned,
        )

    return _make


def _row_exists(conn, table: str, row_id) -> bool:
    return (
        conn.execute(
            sa.text(f"SELECT 1 FROM {table} WHERE id = CAST(:id AS uuid)"),  # noqa: S608
            {"id": row_id},
        ).fetchone()
        is not None
    )


def _linked_metric_count(conn, requirement_id) -> int:
    return _scalar(
        conn,
        "SELECT COUNT(*) FROM requirement_metric WHERE requirement_id = CAST(:id AS uuid)",
        id=requirement_id,
    )


def _configuration_attributes(conn, config_id) -> dict:
    raw = _scalar(
        conn,
        "SELECT attributes FROM test_configuration WHERE id = CAST(:id AS uuid)",
        id=config_id,
    )
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


def _pinned_metric_ids(conn, config_id) -> list:
    entries = _configuration_attributes(conn, config_id).get("metrics") or []
    return [entry["id"] for entry in entries]


@pytest.mark.integration
class TestRagasRemoval:
    def test_head_schema_has_no_ragas_backend_type(self, conn):
        """The migration already ran to head, so the type_lookup row is gone."""
        assert _backend_type_id(conn, "ragas") is None

    def test_deletes_ragas_metrics_and_keeps_others(
        self, conn, migration_ops, backend_type, make_metric
    ):
        ragas = make_metric(backend_type("ragas"), "Ragas")
        kept = make_metric(backend_type("deepeval"), "DeepEval")

        _migration.upgrade()

        assert not _row_exists(conn, "metric", ragas)
        assert _row_exists(conn, "metric", kept)
        assert _backend_type_id(conn, "ragas") is None

    def test_is_idempotent(self, conn, migration_ops, backend_type, make_metric):
        make_metric(backend_type("ragas"), "Ragas")

        _migration.upgrade()
        _migration.upgrade()

        assert _backend_type_id(conn, "ragas") is None


@pytest.mark.integration
class TestRequirementLinks:
    def test_requirement_loses_only_the_ragas_link(
        self, conn, migration_ops, backend_type, make_metric, make_requirement
    ):
        ragas = make_metric(backend_type("ragas"), "Ragas")
        kept = make_metric(backend_type("deepeval"), "DeepEval")
        requirement = make_requirement(ragas, kept)

        _migration.upgrade()

        assert _row_exists(conn, "requirement", requirement)
        assert _linked_metric_count(conn, requirement) == 1

    def test_requirement_left_with_no_metrics_is_kept_not_deleted(
        self, conn, migration_ops, backend_type, make_metric, make_requirement
    ):
        """It ends up evaluating nothing, but deleting user-authored content is worse."""
        requirement = make_requirement(make_metric(backend_type("ragas"), "Ragas"))

        _migration.upgrade()

        assert _row_exists(conn, "requirement", requirement)
        assert _linked_metric_count(conn, requirement) == 0


@pytest.mark.integration
class TestPinnedMetricSnapshots:
    """A test configuration can pin exact metric ids, which execution prefers over the
    test set's own metrics. A deleted metric must not be left dangling there."""

    def test_ragas_id_is_pruned_and_others_survive(
        self, conn, migration_ops, backend_type, make_metric, make_test_configuration
    ):
        ragas = make_metric(backend_type("ragas"), "Ragas")
        kept = make_metric(backend_type("deepeval"), "DeepEval")
        config = make_test_configuration(ragas, kept)

        _migration.upgrade()

        assert _pinned_metric_ids(conn, config) == [str(kept)]
        assert _configuration_attributes(conn, config)["metrics_source"] == "execution_time"

    def test_config_pinning_only_ragas_drops_the_pin_and_its_source(
        self, conn, migration_ops, backend_type, make_metric, make_test_configuration
    ):
        """Execution reads an empty list as "no pin" and falls back to the test set's
        metrics, so leaving metrics_source='execution_time' behind would misreport what
        the run actually evaluates."""
        config = make_test_configuration(make_metric(backend_type("ragas"), "Ragas"))

        _migration.upgrade()

        attributes = _configuration_attributes(conn, config)
        assert "metrics" not in attributes
        assert "metrics_source" not in attributes


class TestRlsIsLiftedForEveryTableTouched:
    """Static checks -- Testcontainers runs as superuser, which bypasses RLS entirely.

    Every table this migration touches is FORCE ROW LEVEL SECURITY with a strict
    ``tenant_isolation`` policy built on ``current_setting('app.current_organization')``
    with no missing_ok argument. A migration binds no organization, so with RLS left on
    the statement raises ``unrecognized configuration parameter`` in production while
    passing here. Nothing at runtime can catch that, so assert on the source.
    """

    def test_every_written_table_has_rls_lifted(self):
        written = set()
        for statement in _migration.CLEANUP_STATEMENTS:
            match = re.search(r"\b(?:DELETE FROM|UPDATE)\s+([a-z_]+)", statement)
            assert match, f"could not read the target table out of: {statement[:60]}"
            written.add(match.group(1))

        missing = written - set(_migration.RLS_TABLES)
        assert not missing, f"RLS not lifted for tables this migration writes to: {missing}"

    def test_tables_read_without_being_written_are_covered(self):
        """``requirement`` is only read, by the orphan warning, and both type_lookup
        templates span every organization."""
        assert {"requirement", "type_lookup"} <= set(_migration.RLS_TABLES)

    def test_rls_is_restored_with_both_enable_and_force(self):
        source = _MIGRATION_PATH.read_text()
        assert "ENABLE ROW LEVEL SECURITY" in source
        assert "FORCE ROW LEVEL SECURITY" in source, (
            "re-enabling without FORCE would silently exempt the table owner"
        )
