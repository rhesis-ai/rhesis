"""The c4d8e1f2a3b6 cleanup: children of soft-deleted requirements lose the link.

Runs on ``admin_test_db``, like the migration, so the UPDATE sees every org.
Everything rolls back at teardown.
"""

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

_MIGRATION_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "apps/backend/src/rhesis/backend/alembic/versions"
    / "c4d8e1f2a3b6_unlink_children_of_deleted_requirements.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("unlink_deleted_parents", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration()


@pytest.fixture
def migration_ops(admin_test_db):
    ctx = MigrationContext.configure(admin_test_db.connection())
    with Operations.context(ctx):
        yield


def _requirement(conn, org_id, user_id, parent_id=None, deleted=False) -> uuid.UUID:
    row_id = uuid.uuid4()
    conn.execute(
        sa.text(
            "INSERT INTO requirement (id, name, organization_id, user_id, parent_id, deleted_at) "
            "VALUES (:id, :name, :org, :user, :parent, CASE WHEN :deleted THEN now() END)"
        ),
        {
            "id": row_id,
            "name": f"Req {row_id.hex[:8]}",
            "org": org_id,
            "user": user_id,
            "parent": parent_id,
            "deleted": deleted,
        },
    )
    return row_id


def _parent_of(conn, row_id):
    return conn.execute(
        sa.text("SELECT parent_id FROM requirement WHERE id = :id"), {"id": row_id}
    ).scalar_one()


@pytest.mark.unit
def test_unlinks_only_children_of_deleted_parents(
    admin_test_db, migration_ops, test_org_id, authenticated_user_id
):
    conn = admin_test_db.connection()
    gone = _requirement(conn, test_org_id, authenticated_user_id, deleted=True)
    live = _requirement(conn, test_org_id, authenticated_user_id)
    orphan = _requirement(conn, test_org_id, authenticated_user_id, parent_id=gone)
    kept = _requirement(conn, test_org_id, authenticated_user_id, parent_id=live)

    _migration.upgrade()

    assert _parent_of(conn, orphan) is None
    assert _parent_of(conn, kept) == live
