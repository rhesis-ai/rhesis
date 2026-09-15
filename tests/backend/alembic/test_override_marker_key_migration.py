"""Pre-merge confidence tests for the override-marker key rename (a0005ovrdkey).

TEMPORARY: delete once that migration has shipped everywhere.

The migration rewrites a key *inside* nested JSONB, which is the part worth
pinning: the paths, the array ordering, and that the rest of the marker survives.
It uses two SQL templates -- one for an object of entries, one for an array of
them -- and ``test_result`` exercises both (``test_metrics -> metrics`` is the
object shape, ``test_output -> conversation_summary`` the array shape). The three
trace paths run the object template with a different path, so they add no new
SQL to cover and would need a project row to insert against.

Drives ``upgrade()``/``downgrade()`` directly against the ``test_db``
connection inside an ``Operations.context``, so everything rolls back at
teardown.
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
    Path(__file__).parent.parent.parent.parent
    / "apps"
    / "backend"
    / "src"
    / "rhesis"
    / "backend"
    / "alembic"
    / "versions"
    / "a0005_rename_override_marker_key.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "override_marker_key_migration_under_test", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()

_ANNOTATION_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def migration_ops(test_db):
    """Activates an Operations context so the migration's bare ``op.xxx`` calls resolve."""
    ctx = MigrationContext.configure(test_db.connection())
    with Operations.context(ctx):
        yield


def _marker(key: str) -> dict:
    """An override marker with every field the writers put on one."""
    return {
        "original_value": True,
        key: _ANNOTATION_ID,
        "overridden_by": "22222222-2222-2222-2222-222222222222",
        "overridden_at": "2026-09-15T10:00:00+00:00",
        "original_error": "timed out",
    }


def _insert_result(conn, *, org_id, user_id, test_metrics=None, test_output=None) -> uuid.UUID:
    row = conn.execute(
        sa.text(
            """
            INSERT INTO test_result (organization_id, user_id, test_metrics, test_output)
            VALUES (
                CAST(:org_id AS uuid), CAST(:user_id AS uuid),
                CAST(:metrics AS jsonb), CAST(:output AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "org_id": org_id,
            "user_id": user_id,
            "metrics": None if test_metrics is None else json.dumps(test_metrics),
            "output": None if test_output is None else json.dumps(test_output),
        },
    ).fetchone()
    return row[0]


def _read(conn, column: str, result_id: uuid.UUID):
    raw = conn.execute(
        sa.text(f"SELECT {column} FROM test_result WHERE id = CAST(:id AS uuid)"),  # noqa: S608
        {"id": result_id},
    ).scalar()
    return json.loads(raw) if isinstance(raw, str) else raw


@pytest.mark.integration
class TestMetricsObjectShape:
    def test_renames_the_key_and_keeps_the_rest_of_the_marker(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        result_id = _insert_result(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            test_metrics={
                "metrics": {
                    "Answer Fluency": {
                        "is_successful": False,
                        "override": _marker("review_id"),
                    }
                },
                "execution_time": 120,
            },
        )

        _migration.upgrade()

        override = _read(conn, "test_metrics", result_id)["metrics"]["Answer Fluency"][
            "override"
        ]
        assert override["annotation_id"] == _ANNOTATION_ID
        assert "review_id" not in override
        assert override["original_value"] is True
        assert override["original_error"] == "timed out"
        assert override["overridden_at"] == "2026-09-15T10:00:00+00:00"

    def test_leaves_metrics_without_an_override_alone(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        result_id = _insert_result(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            test_metrics={
                "metrics": {
                    "Overridden": {"is_successful": False, "override": _marker("review_id")},
                    "Untouched": {"is_successful": True, "score": 0.9},
                },
                "execution_time": 7,
            },
        )

        _migration.upgrade()

        metrics = _read(conn, "test_metrics", result_id)["metrics"]
        assert metrics["Untouched"] == {"is_successful": True, "score": 0.9}
        assert "annotation_id" in metrics["Overridden"]["override"]

    def test_sibling_keys_on_the_column_survive(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        result_id = _insert_result(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            test_metrics={
                "metrics": {"M": {"is_successful": False, "override": _marker("review_id")}},
                "execution_time": 42,
            },
        )

        _migration.upgrade()

        assert _read(conn, "test_metrics", result_id)["execution_time"] == 42

    def test_a_result_with_no_metrics_is_not_touched(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        result_id = _insert_result(conn, org_id=test_org_id, user_id=authenticated_user_id)

        _migration.upgrade()

        assert _read(conn, "test_metrics", result_id) is None


@pytest.mark.integration
class TestConversationSummaryArrayShape:
    def test_renames_the_key_and_preserves_turn_order(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        result_id = _insert_result(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            test_output={
                "conversation_summary": [
                    {"turn": 1, "success": True},
                    {"turn": 2, "success": False, "override": _marker("review_id")},
                    {"turn": 3, "success": True},
                ]
            },
        )

        _migration.upgrade()

        summary = _read(conn, "test_output", result_id)["conversation_summary"]
        assert [turn["turn"] for turn in summary] == [1, 2, 3]
        assert summary[1]["override"]["annotation_id"] == _ANNOTATION_ID
        assert "review_id" not in summary[1]["override"]
        assert "override" not in summary[0]


@pytest.mark.integration
class TestRoundTrip:
    def test_downgrade_restores_the_old_key(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        before = {
            "metrics": {"M": {"is_successful": False, "override": _marker("review_id")}},
            "execution_time": 3,
        }
        result_id = _insert_result(
            conn, org_id=test_org_id, user_id=authenticated_user_id, test_metrics=before
        )

        _migration.upgrade()
        _migration.downgrade()

        assert _read(conn, "test_metrics", result_id) == before

    def test_upgrade_is_idempotent(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        result_id = _insert_result(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            test_metrics={
                "metrics": {"M": {"is_successful": False, "override": _marker("review_id")}}
            },
        )

        _migration.upgrade()
        after_first = _read(conn, "test_metrics", result_id)
        _migration.upgrade()

        assert _read(conn, "test_metrics", result_id) == after_first
