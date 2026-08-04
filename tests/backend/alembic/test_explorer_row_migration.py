"""Pre-merge confidence tests for the ``explorer_row`` backfill migration.

TEMPORARY: delete once that migration has shipped everywhere.

Drives the migration's ``upgrade()``/``downgrade()`` directly against the
``test_db`` connection inside an ``Operations.context``, so the DDL rolls back
at teardown. Skips the ``client`` fixture: ``upgrade()`` holds ACCESS EXCLUSIVE
locks that a second connection would block on.

Testcontainers runs as superuser, so it can't catch a broken RLS disable/enable
dance -- that's on the migration's own fail-loud verification, not this file.
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
    / "7dd69fe35db5_add_explorer_row_to_test_set_and_test.py"
)

_EXPLORER_BEHAVIOR_NAME = "Adaptive Testing"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "explorer_row_migration_under_test", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()


@pytest.fixture
def migration_ops(test_db):
    """Activates an Operations context so the migration's bare ``op.xxx`` calls resolve."""
    ctx = MigrationContext.configure(test_db.connection())
    with Operations.context(ctx):
        yield


def _insert_test_set(conn, *, org_id, user_id, attributes) -> uuid.UUID:
    attrs_json = None if attributes is None else json.dumps(attributes)
    row = conn.execute(
        sa.text(
            """
            INSERT INTO test_set (name, organization_id, user_id, visibility, attributes)
            VALUES (
                :name, CAST(:org_id AS uuid), CAST(:user_id AS uuid), 'organization',
                CAST(:attrs AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "name": f"explorer_row migration test {uuid.uuid4().hex[:8]}",
            "org_id": org_id,
            "user_id": user_id,
            "attrs": attrs_json,
        },
    ).fetchone()
    return row[0]


def _insert_test(conn, *, org_id, user_id) -> uuid.UUID:
    row = conn.execute(
        sa.text(
            """
            INSERT INTO test (organization_id, user_id)
            VALUES (CAST(:org_id AS uuid), CAST(:user_id AS uuid))
            RETURNING id
            """
        ),
        {"org_id": org_id, "user_id": user_id},
    ).fetchone()
    return row[0]


def _associate(conn, *, test_id, test_set_id, org_id, user_id) -> None:
    conn.execute(
        sa.text(
            """
            INSERT INTO test_test_set (test_id, test_set_id, organization_id, user_id)
            VALUES (
                CAST(:test_id AS uuid), CAST(:test_set_id AS uuid),
                CAST(:org_id AS uuid), CAST(:user_id AS uuid)
            )
            """
        ),
        {"test_id": test_id, "test_set_id": test_set_id, "org_id": org_id, "user_id": user_id},
    )


def _explorer_row(conn, table: str, row_id: uuid.UUID) -> bool:
    return conn.execute(
        sa.text(f"SELECT explorer_row FROM {table} WHERE id = CAST(:id AS uuid)"),  # noqa: S608
        {"id": row_id},
    ).scalar()


def _test_set_attributes(conn, test_set_id: uuid.UUID):
    raw = conn.execute(
        sa.text("SELECT attributes FROM test_set WHERE id = CAST(:id AS uuid)"),
        {"id": test_set_id},
    ).scalar()
    return json.loads(raw) if isinstance(raw, str) else raw


@pytest.mark.integration
class TestColumnShape:
    """The column exists on both tables as boolean/not-null/default-false."""

    @pytest.mark.parametrize("table", ["test_set", "test"])
    def test_column_is_boolean_not_null_default_false(self, test_db, table):
        row = (
            test_db.connection()
            .execute(
                sa.text(
                    "SELECT data_type, is_nullable, column_default "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :t "
                    "AND column_name = 'explorer_row'"
                ),
                {"t": table},
            )
            .fetchone()
        )

        assert row is not None, f"explorer_row column missing on {table}"
        data_type, is_nullable, column_default = row
        assert data_type == "boolean"
        assert is_nullable == "NO"
        assert column_default is not None and "false" in column_default.lower()


@pytest.mark.integration
class TestBackfillLogic:
    """Re-running upgrade() against freshly seeded rows exercises the real backfill SQL."""

    def test_marker_only_test_set_becomes_true(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": [_EXPLORER_BEHAVIOR_NAME]}},
        )

        _migration.upgrade()

        assert _explorer_row(conn, "test_set", ts_id) is True

    def test_marker_among_other_behaviors_becomes_true(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": ["Safety", _EXPLORER_BEHAVIOR_NAME]}},
        )

        _migration.upgrade()

        assert _explorer_row(conn, "test_set", ts_id) is True

    def test_regular_test_set_stays_false(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": ["Safety"]}},
        )

        _migration.upgrade()

        assert _explorer_row(conn, "test_set", ts_id) is False

    @pytest.mark.parametrize(
        "attributes",
        [
            None,
            {},
            {"metadata": "not-an-object"},
            {"unexpected": True},
        ],
    )
    def test_null_or_malformed_attributes_stay_false_without_error(
        self, test_db, migration_ops, test_org_id, authenticated_user_id, attributes
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn, org_id=test_org_id, user_id=authenticated_user_id, attributes=attributes
        )

        _migration.upgrade()  # must not raise

        assert _explorer_row(conn, "test_set", ts_id) is False

    def test_test_associated_with_an_explorer_set_becomes_true(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": [_EXPLORER_BEHAVIOR_NAME]}},
        )
        t_id = _insert_test(conn, org_id=test_org_id, user_id=authenticated_user_id)
        _associate(
            conn,
            test_id=t_id,
            test_set_id=ts_id,
            org_id=test_org_id,
            user_id=authenticated_user_id,
        )

        _migration.upgrade()

        assert _explorer_row(conn, "test_set", ts_id) is True
        assert _explorer_row(conn, "test", t_id) is True

    def test_test_only_in_regular_sets_stays_false(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": ["Safety"]}},
        )
        t_id = _insert_test(conn, org_id=test_org_id, user_id=authenticated_user_id)
        _associate(
            conn,
            test_id=t_id,
            test_set_id=ts_id,
            org_id=test_org_id,
            user_id=authenticated_user_id,
        )

        _migration.upgrade()

        assert _explorer_row(conn, "test", t_id) is False

    def test_test_shared_between_an_explorer_and_a_regular_set_becomes_true(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        explorer_ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": [_EXPLORER_BEHAVIOR_NAME]}},
        )
        regular_ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": ["Safety"]}},
        )
        t_id = _insert_test(conn, org_id=test_org_id, user_id=authenticated_user_id)
        _associate(
            conn,
            test_id=t_id,
            test_set_id=explorer_ts_id,
            org_id=test_org_id,
            user_id=authenticated_user_id,
        )
        _associate(
            conn,
            test_id=t_id,
            test_set_id=regular_ts_id,
            org_id=test_org_id,
            user_id=authenticated_user_id,
        )

        _migration.upgrade()

        assert _explorer_row(conn, "test", t_id) is True

    def test_idempotent_rerun_changes_nothing(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": [_EXPLORER_BEHAVIOR_NAME]}},
        )
        t_id = _insert_test(conn, org_id=test_org_id, user_id=authenticated_user_id)
        _associate(
            conn,
            test_id=t_id,
            test_set_id=ts_id,
            org_id=test_org_id,
            user_id=authenticated_user_id,
        )

        _migration.upgrade()
        _migration.upgrade()  # must not raise, must not change the outcome

        assert _explorer_row(conn, "test_set", ts_id) is True
        assert _explorer_row(conn, "test", t_id) is True


@pytest.mark.integration
class TestMarkerStripping:
    """upgrade() removes the "Adaptive Testing" marker from attributes once
    explorer_row is verified."""

    def test_marker_only_drops_the_whole_behaviors_key(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": [_EXPLORER_BEHAVIOR_NAME]}},
        )

        _migration.upgrade()

        assert _explorer_row(conn, "test_set", ts_id) is True
        attrs = _test_set_attributes(conn, ts_id)
        assert "behaviors" not in attrs.get("metadata", {})

    def test_marker_among_other_behaviors_only_removes_the_marker(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": ["Safety", _EXPLORER_BEHAVIOR_NAME]}},
        )

        _migration.upgrade()

        attrs = _test_set_attributes(conn, ts_id)
        assert attrs["metadata"]["behaviors"] == ["Safety"]

    def test_regular_test_set_attributes_are_untouched(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": ["Safety"]}},
        )

        _migration.upgrade()

        attrs = _test_set_attributes(conn, ts_id)
        assert attrs["metadata"]["behaviors"] == ["Safety"]

    def test_idempotent_rerun_does_not_error_once_marker_is_gone(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": [_EXPLORER_BEHAVIOR_NAME]}},
        )

        _migration.upgrade()
        _migration.upgrade()  # marker is already gone; must not raise

        assert _explorer_row(conn, "test_set", ts_id) is True


@pytest.mark.integration
class TestDowngradeRestoresMarker:
    """downgrade() writes the marker back onto every row explorer_row still
    flags, reading that column before dropping it."""

    def test_restores_the_marker_alongside_other_behaviors(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": ["Safety"]}},
        )
        conn.execute(
            sa.text("UPDATE test_set SET explorer_row = true WHERE id = CAST(:id AS uuid)"),
            {"id": ts_id},
        )

        _migration.downgrade()

        attrs = _test_set_attributes(conn, ts_id)
        assert attrs["metadata"]["behaviors"] == ["Safety", _EXPLORER_BEHAVIOR_NAME]

    def test_restores_the_marker_from_scratch_when_attributes_is_null(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn, org_id=test_org_id, user_id=authenticated_user_id, attributes=None
        )
        conn.execute(
            sa.text("UPDATE test_set SET explorer_row = true WHERE id = CAST(:id AS uuid)"),
            {"id": ts_id},
        )

        _migration.downgrade()

        attrs = _test_set_attributes(conn, ts_id)
        assert attrs["metadata"]["behaviors"] == [_EXPLORER_BEHAVIOR_NAME]

    def test_leaves_non_explorer_rows_untouched(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": ["Safety"]}},
        )

        _migration.downgrade()

        attrs = _test_set_attributes(conn, ts_id)
        assert attrs["metadata"]["behaviors"] == ["Safety"]

    @pytest.mark.parametrize(
        "attributes",
        [
            {"metadata": "not-an-object"},
            "not-an-object",
            {"metadata": {"behaviors": "not-an-array"}},
        ],
    )
    def test_restores_the_marker_without_raising_when_attributes_shape_is_malformed(
        self, test_db, migration_ops, test_org_id, authenticated_user_id, attributes
    ):
        """jsonb_set() errors on a scalar target ("cannot set path in scalar") --
        the restore UPDATE must fall back to an empty object/array instead of
        raising when metadata (or attributes itself) isn't the expected shape."""
        conn = test_db.connection()
        ts_id = _insert_test_set(
            conn, org_id=test_org_id, user_id=authenticated_user_id, attributes=attributes
        )
        conn.execute(
            sa.text("UPDATE test_set SET explorer_row = true WHERE id = CAST(:id AS uuid)"),
            {"id": ts_id},
        )

        _migration.downgrade()  # must not raise

        attrs = _test_set_attributes(conn, ts_id)
        assert attrs["metadata"]["behaviors"] == [_EXPLORER_BEHAVIOR_NAME]

    def test_column_is_dropped(self, test_db, migration_ops):
        conn = test_db.connection()

        _migration.downgrade()

        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'test_set' AND column_name = 'explorer_row'"
            )
        ).fetchone()
        assert exists is None


@pytest.mark.integration
class TestDowngradeUpgradeRoundTrip:
    def test_round_trip_rederives_correct_values_from_scratch(
        self, test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = test_db.connection()

        _migration.downgrade()  # drop both columns

        ts_id = _insert_test_set(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": [_EXPLORER_BEHAVIOR_NAME]}},
        )
        t_id = _insert_test(conn, org_id=test_org_id, user_id=authenticated_user_id)
        _associate(
            conn,
            test_id=t_id,
            test_set_id=ts_id,
            org_id=test_org_id,
            user_id=authenticated_user_id,
        )

        _migration.upgrade()  # re-add columns and re-derive from scratch

        assert _explorer_row(conn, "test_set", ts_id) is True
        assert _explorer_row(conn, "test", t_id) is True
