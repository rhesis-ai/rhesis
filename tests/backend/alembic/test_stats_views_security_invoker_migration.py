"""Round trip for the migration that makes the stats views security_invoker.

Runs inside the ``admin_test_db`` transaction, so every DDL rolls back at
teardown. Downgrade must restore exactly what b3e7c91d4a20 + e5a1c7d93b42
created, and upgrade must restore the definitions c47fd570587b left.

f1a7c3e9d2b5 has since appended columns to three of the views, which a
replace-in-place can't take away, so each test first steps that one back
and restores it at the end.
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
_VIEWS = ("v_test_result_stats", "v_metric_stats", "v_test_run_stats", "v_test_stats")


def _load(filename: str):
    spec = importlib.util.spec_from_file_location(f"mig_{filename[:12]}", _VERSIONS / filename)
    assert spec and spec.loader, f"Unable to load migration {filename} from {_VERSIONS}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load("c47fd570587b_stats_views_security_invoker.py")
_redesign = _load("b3e7c91d4a20_redesign_insights_stats_views.py")
_duration = _load("e5a1c7d93b42_add_run_duration_to_test_run_stats.py")
_impact = _load("f1a7c3e9d2b5_stats_views_impact_and_parent.py")


@pytest.fixture
def conn(admin_test_db):
    connection = admin_test_db.connection()
    with Operations.context(MigrationContext.configure(connection)):
        _impact.downgrade()
        yield connection
        _impact.upgrade()


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


def test_downgrade_restores_previous_definitions_and_upgrade_restores_its_own(conn):
    at_c47 = _snapshot(conn)
    assert set(at_c47) == set(_VIEWS)
    assert all(options == ["security_invoker=true"] for _, options in at_c47.values())

    _redesign.upgrade()
    _duration.upgrade()
    previous = _snapshot(conn)

    _migration.downgrade()
    assert _snapshot(conn) == previous

    _migration.upgrade()
    assert _snapshot(conn) == at_c47


def test_round_trip_keeps_grants(conn):
    """Views are replaced in place, so roles granted SELECT (app role, readers) keep it."""
    before = _grants(conn)
    assert all(before.values()), before

    _migration.downgrade()
    assert _grants(conn) == before

    _migration.upgrade()
    assert _grants(conn) == before
