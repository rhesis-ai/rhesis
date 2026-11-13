"""Round trip for the migration that adds impact and parent to the stats views.

Runs inside the ``admin_test_db`` transaction, so every DDL rolls back at
teardown. Downgrade must restore exactly what c47fd570587b created, and
upgrade must restore the head definitions.
"""

import importlib.util
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

pytestmark = pytest.mark.skipif(
    os.environ.get("RHESIS_SKIP_MIGRATIONS", "").lower() in ("1", "true", "yes"),
    reason="Depends on the head schema; skipped when RHESIS_SKIP_MIGRATIONS is set.",
)

_VERSIONS = Path(__file__).parents[3] / "apps/backend/src/rhesis/backend/alembic/versions"
_VIEWS = ("v_test_result_stats", "v_metric_stats", "v_test_stats")
_NEW_COLUMNS = ("impact_id", "impact_name", "requirement_parent_id", "requirement_parent_name")


def _load(filename: str):
    spec = importlib.util.spec_from_file_location(f"mig_{filename[:12]}", _VERSIONS / filename)
    assert spec and spec.loader, f"Unable to load migration {filename} from {_VERSIONS}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load("f1a7c3e9d2b5_stats_views_impact_and_parent.py")
_previous = _load("c47fd570587b_stats_views_security_invoker.py")


@pytest.fixture
def conn(admin_test_db):
    connection = admin_test_db.connection()
    with Operations.context(MigrationContext.configure(connection)):
        yield connection


def _grants(conn) -> dict:
    rows = conn.execute(
        sa.text("SELECT relname, relacl::text FROM pg_class WHERE relname = ANY(:views)"),
        {"views": list(_VIEWS)},
    ).fetchall()
    return dict(rows)


def _snapshot(conn) -> dict:
    rows = conn.execute(
        sa.text(
            "SELECT c.relname, pg_get_viewdef(c.oid), COALESCE(c.reloptions, '{}')"
            " FROM pg_class c WHERE c.relname = ANY(:views) AND c.relkind = 'v'"
        ),
        {"views": list(_VIEWS)},
    ).fetchall()
    return {name: (definition, list(options)) for name, definition, options in rows}


def _columns(conn, view: str) -> list:
    rows = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = :view ORDER BY ordinal_position"
        ),
        {"view": view},
    ).fetchall()
    return [row[0] for row in rows]


def test_head_views_end_with_the_new_columns(conn):
    for view in _VIEWS:
        assert tuple(_columns(conn, view)[-4:]) == _NEW_COLUMNS, view


def test_downgrade_restores_previous_definitions_and_upgrade_restores_head(conn):
    head = _snapshot(conn)
    assert set(head) == set(_VIEWS)
    assert all(options == ["security_invoker=true"] for _, options in head.values())

    _migration.downgrade()
    previous = _snapshot(conn)
    assert all(options == ["security_invoker=true"] for _, options in previous.values())
    for view in _VIEWS:
        assert not set(_NEW_COLUMNS) & set(_columns(conn, view)), view

    # c47fd570587b replaces in place, so this only leaves the views unchanged if
    # the downgrade already recreated exactly its definitions.
    _previous.upgrade()
    assert _snapshot(conn) == previous

    _migration.upgrade()
    assert _snapshot(conn) == head


def test_round_trip_keeps_grants(conn):
    """The downgrade drops the views, so it must give back the SELECTs it found."""
    before = _grants(conn)
    assert all(before.values()), before

    _migration.downgrade()
    assert _grants(conn) == before

    _migration.upgrade()
    assert _grants(conn) == before
