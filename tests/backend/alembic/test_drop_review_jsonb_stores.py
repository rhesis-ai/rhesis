"""Pre-merge confidence tests for the JSONB review drop (a3f6c81d05b2).

TEMPORARY: delete once that migration has shipped everywhere.

This migration is destructive and its downgrade cannot undo it, so what is worth
pinning is that it removes exactly what it claims to and nothing else: the two
columns, and the ``reviews`` key on tuning cases without disturbing the rest of
the shared ``test_metadata`` object.

Drives ``upgrade()``/``downgrade()`` directly against the ``admin_test_db`` connection
inside an ``Operations.context``, so everything rolls back at teardown. The admin
role is required because ``ALTER TABLE`` may only be issued by the table owner,
matching production where migrations run as the admin role. The suite
migrates to head before it runs, so this migration has already been applied: the
pre-migration schema is reached by calling ``downgrade()`` first rather than by
hand-adding the columns, which also exercises the downgrade for real.
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
    / "a3f6c81d05b2_drop_review_jsonb_stores.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("drop_review_jsonb_under_test", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()


@pytest.fixture
def migration_ops(admin_test_db):
    """Activates an Operations context so the migration's bare ``op.xxx`` calls resolve."""
    ctx = MigrationContext.configure(admin_test_db.connection())
    with Operations.context(ctx):
        yield


def _rebind_org(conn, org_id) -> None:
    """Put the tenant GUC back after the migration walked every organization."""
    conn.execute(
        sa.text(
            "SELECT set_config('app.current_organization', :org_id, true),"
            "       set_config('app.current_project', '', true)"
        ),
        {"org_id": str(org_id)},
    )


def _column_exists(conn, table: str, column: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).scalar()
    )


def _insert_test(conn, *, org_id, user_id, metadata) -> uuid.UUID:
    return conn.execute(
        sa.text(
            """
            INSERT INTO test (organization_id, user_id, test_metadata)
            VALUES (
                CAST(:org_id AS uuid), CAST(:user_id AS uuid), CAST(:metadata AS jsonb)
            )
            RETURNING id
            """
        ),
        {"org_id": str(org_id), "user_id": str(user_id), "metadata": json.dumps(metadata)},
    ).scalar()


def _metadata_of(conn, test_id) -> dict:
    return conn.execute(
        sa.text("SELECT test_metadata FROM test WHERE id = CAST(:id AS uuid)"),
        {"id": str(test_id)},
    ).scalar()


class TestTheColumnsGo:
    def test_neither_column_exists_at_head(self, admin_test_db):
        conn = admin_test_db.connection()
        assert not _column_exists(conn, "test_result", "test_reviews")
        assert not _column_exists(conn, "trace", "trace_reviews")

    def test_a_downgrade_and_upgrade_round_trip_drops_them_again(
        self, admin_test_db, migration_ops
    ):
        conn = admin_test_db.connection()
        _migration.downgrade()
        assert _column_exists(conn, "test_result", "test_reviews")
        assert _column_exists(conn, "trace", "trace_reviews")

        _migration.upgrade()

        assert not _column_exists(conn, "test_result", "test_reviews")
        assert not _column_exists(conn, "trace", "trace_reviews")

    def test_downgrade_puts_the_columns_back_nullable(self, admin_test_db, migration_ops):
        conn = admin_test_db.connection()
        _migration.downgrade()

        for table, column in (("test_result", "test_reviews"), ("trace", "trace_reviews")):
            row = conn.execute(
                sa.text(
                    "SELECT data_type, is_nullable FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c"
                ),
                {"t": table, "c": column},
            ).one()
            assert row.data_type == "jsonb", f"{table}.{column} came back as {row.data_type}"
            assert row.is_nullable == "YES", f"{table}.{column} came back NOT NULL"


class TestTheTuningArray:
    def test_the_reviews_key_is_stripped(
        self, admin_test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = admin_test_db.connection()
        test_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metadata={
                "reviews": [{"decision": "rejected", "comment": "wrong"}],
                "result": {"verdict": "pass"},
            },
        )

        _migration.downgrade()  # so upgrade()'s DROP COLUMNs have something to drop
        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        meta = _metadata_of(conn, test_id)
        assert "reviews" not in meta, meta

    def test_everything_else_in_the_shared_column_survives(
        self, admin_test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        """The column has other writers, so this must remove a key rather than rewrite."""
        conn = admin_test_db.connection()
        test_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metadata={
                "reviews": [{"decision": "accepted"}],
                "result": {"verdict": "0.9", "reasoning": "looks right"},
                "label": "fail",
                "labeler": "Toxicity",
            },
        )

        _migration.downgrade()  # so upgrade()'s DROP COLUMNs have something to drop
        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        meta = _metadata_of(conn, test_id)
        assert "reviews" not in meta
        assert meta["result"] == {"verdict": "0.9", "reasoning": "looks right"}
        assert meta["label"] == "fail"
        assert meta["labeler"] == "Toxicity"

    def test_a_test_without_the_key_is_left_alone(
        self, admin_test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        conn = admin_test_db.connection()
        untouched = {"label": "pass", "labeler": "user", "output": "o"}
        test_id = _insert_test(
            conn, org_id=test_org_id, user_id=authenticated_user_id, metadata=untouched
        )

        _migration.downgrade()  # so upgrade()'s DROP COLUMNs have something to drop
        _migration.upgrade()
        _rebind_org(conn, test_org_id)

        assert _metadata_of(conn, test_id) == untouched

    def test_upgrade_is_idempotent(
        self, admin_test_db, migration_ops, test_org_id, authenticated_user_id
    ):
        """Only the metadata strip can run twice; the DROPs cannot, so it is run alone."""
        conn = admin_test_db.connection()
        test_id = _insert_test(
            conn,
            org_id=test_org_id,
            user_id=authenticated_user_id,
            metadata={"reviews": [{"decision": "accepted"}], "label": "pass"},
        )

        for _ in range(2):
            for org_id in [row[0] for row in conn.execute(_migration._ORGANIZATIONS)]:
                params = {"org_id": str(org_id)}
                conn.execute(_migration._BIND_ORG, params)
                conn.execute(_migration._STRIP_TUNING_REVIEWS, params)
        conn.execute(_migration._UNBIND_ORG)
        _rebind_org(conn, test_org_id)

        meta = _metadata_of(conn, test_id)
        assert "reviews" not in meta
        assert meta["label"] == "pass"
