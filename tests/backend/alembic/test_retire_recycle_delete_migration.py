"""Data-level checks for the migration that retires recycle:delete.

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
    / "db8b66e257cc_retire_recycle_delete_capability.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "retire_recycle_delete_under_test", _MIGRATION_PATH
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


def _perm_id(conn, name):
    return conn.execute(sa.text("SELECT id FROM permission WHERE name = :n"), {"n": name}).scalar()


@pytest.fixture
def make_role(conn, test_org_id):
    def _make(*grants: str):
        role_id = conn.execute(
            sa.text(
                """
                INSERT INTO role (name, display_name, scope, level, is_built_in, organization_id)
                VALUES (:name, :name, 'organization', 50, false, CAST(:org AS uuid))
                RETURNING id
                """
            ),
            {"name": f"custom {uuid.uuid4().hex[:8]}", "org": test_org_id},
        ).scalar()
        for name in grants:
            conn.execute(
                sa.text("INSERT INTO role_permission (role_id, permission_id) VALUES (:r, :p)"),
                {"r": role_id, "p": _perm_id(conn, name)},
            )
        return role_id

    return _make


def _grants(conn, role_id):
    return set(
        conn.execute(
            sa.text(
                "SELECT p.name FROM role_permission rp JOIN permission p "
                "ON p.id = rp.permission_id WHERE rp.role_id = :r"
            ),
            {"r": role_id},
        ).scalars()
    )


@pytest.fixture
def delete_cap_active(conn):
    """Head has already retired recycle:delete; put it back as it was before."""
    conn.execute(sa.text("UPDATE permission SET is_retired = false WHERE name = 'recycle:delete'"))


@pytest.mark.unit
class TestRetireRecycleDelete:
    def test_delete_grant_gains_purge(self, conn, make_role, delete_cap_active, migration_ops):
        role = make_role("recycle:delete")

        _migration.upgrade()

        assert {"recycle:delete", "recycle:purge"} <= _grants(conn, role)

    def test_existing_purge_grant_is_not_duplicated(
        self, conn, make_role, delete_cap_active, migration_ops
    ):
        role = make_role("recycle:delete", "recycle:purge")

        _migration.upgrade()
        _migration.upgrade()

        count = conn.execute(
            sa.text(
                "SELECT count(*) FROM role_permission WHERE role_id = :r AND permission_id = :p"
            ),
            {"r": role, "p": _perm_id(conn, "recycle:purge")},
        ).scalar()
        assert count == 1

    def test_roles_without_delete_are_untouched(
        self, conn, make_role, delete_cap_active, migration_ops
    ):
        role = make_role("recycle:restore")

        _migration.upgrade()

        assert _grants(conn, role) == {"recycle:restore"}

    def test_delete_capability_is_retired(self, conn, delete_cap_active, migration_ops):
        _migration.upgrade()

        retired = conn.execute(
            sa.text("SELECT is_retired FROM permission WHERE name = 'recycle:delete'")
        ).scalar()
        assert retired is True
