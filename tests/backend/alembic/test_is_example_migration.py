"""Backfill and reversibility of the is_example migration (a9828a095ff7).

Seeds the example with ``load_initial_data``, adds rows a user could plausibly
make with the same names, then drops and re-adds the column so the backfill has
to find the example rows again on its own.

Runs on ``admin_test_db`` because the migration alters tables, but the backfill
itself runs as the RLS-enforced app role: the production migration role is not
a superuser, so an unscoped UPDATE there would match nothing. Everything rolls
back at teardown.
"""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

from rhesis.backend.app.services.organization import EXAMPLE_PROJECT_NAME, load_initial_data

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
    / "a9828a095ff7_add_is_example_to_seeded_tables.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("is_example_migration", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()


@pytest.fixture
def migration_ops(admin_test_db):
    ctx = MigrationContext.configure(admin_test_db.connection())
    with Operations.context(ctx):
        yield


def _is_example(conn, table: str, row_id) -> bool:
    return conn.execute(
        sa.text(f"SELECT is_example FROM {table} WHERE id = :id"), {"id": row_id}
    ).scalar_one()


@pytest.mark.unit
def test_backfill_marks_only_the_seeded_example(
    admin_test_db, migration_ops, test_org_id, authenticated_user_id
):
    load_initial_data(admin_test_db, test_org_id, authenticated_user_id)
    admin_test_db.flush()
    conn = admin_test_db.connection()

    example_project_id = conn.execute(
        sa.text("SELECT id FROM project WHERE organization_id = :org AND name = :name"),
        {"org": test_org_id, "name": EXAMPLE_PROJECT_NAME},
    ).scalar_one()
    own_project_id = uuid.uuid4()
    conn.execute(
        sa.text(
            "INSERT INTO project (id, name, organization_id, user_id) "
            "VALUES (:id, 'Own Project', :org, :user)"
        ),
        {"id": own_project_id, "org": test_org_id, "user": authenticated_user_id},
    )
    # Same name as the seeded endpoint, but in the user's own project.
    own_endpoint_id = conn.execute(
        sa.text(
            "INSERT INTO endpoint (name, connection_type, environment, config_source, "
            "response_format, organization_id, user_id, project_id) "
            "VALUES (:name, 'REST', 'development', 'manual', 'json', :org, :user, :project) "
            "RETURNING id"
        ),
        {
            "name": _migration._EXAMPLE_ENDPOINT_NAME,
            "org": test_org_id,
            "user": authenticated_user_id,
            "project": own_project_id,
        },
    ).scalar_one()
    own_test_id = conn.execute(
        sa.text(
            "INSERT INTO test (organization_id, user_id, project_id) "
            "VALUES (:org, :user, :project) RETURNING id"
        ),
        {"org": test_org_id, "user": authenticated_user_id, "project": own_project_id},
    ).scalar_one()

    _migration.downgrade()
    _migration.add_columns()
    # Backfill under an RLS-enforced role, like the non-superuser migration role in production.
    conn.execute(sa.text('SET ROLE "rhesis-app"'))
    try:
        _migration.backfill()
    finally:
        conn.execute(sa.text("RESET ROLE"))

    assert _is_example(conn, "project", example_project_id) is True
    assert _is_example(conn, "project", own_project_id) is False
    assert _is_example(conn, "endpoint", own_endpoint_id) is False
    assert _is_example(conn, "test", own_test_id) is False

    seeded_endpoints = conn.execute(
        sa.text("SELECT is_example FROM endpoint WHERE project_id = :project"),
        {"project": example_project_id},
    ).all()
    assert seeded_endpoints and all(row.is_example for row in seeded_endpoints)

    seeded_tests = conn.execute(
        sa.text(
            "SELECT t.is_example FROM test t JOIN prompt p ON p.id = t.prompt_id "
            "WHERE t.organization_id = :org AND p.content IN :prompts"
        ).bindparams(sa.bindparam("prompts", expanding=True)),
        {"org": test_org_id, "prompts": _migration._EXAMPLE_PROMPTS},
    ).all()
    # The shared test org may already hold an earlier seeding, so check every copy.
    assert len(seeded_tests) >= len(_migration._EXAMPLE_PROMPTS)
    assert all(row.is_example for row in seeded_tests)

    seeded_test_sets = conn.execute(
        sa.text("SELECT is_example FROM test_set WHERE organization_id = :org AND name = :name"),
        {"org": test_org_id, "name": _migration._EXAMPLE_TEST_SET_NAME},
    ).all()
    assert seeded_test_sets and all(row.is_example for row in seeded_test_sets)


@pytest.mark.unit
def test_downgrade_drops_the_column(admin_test_db, migration_ops):
    _migration.downgrade()
    conn = admin_test_db.connection()
    remaining = conn.execute(
        sa.text(
            "SELECT table_name FROM information_schema.columns "
            "WHERE column_name = 'is_example' AND table_name IN :tables"
        ).bindparams(sa.bindparam("tables", expanding=True)),
        {"tables": list(_migration._TABLES)},
    ).scalars()
    assert list(remaining) == []
