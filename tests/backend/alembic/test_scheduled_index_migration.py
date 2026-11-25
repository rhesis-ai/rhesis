"""The partial index the schedule dispatcher scans: present at head, and round-trips."""

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
_INDEX = "ix_test_configuration_scheduled"


def _load(filename: str):
    spec = importlib.util.spec_from_file_location(f"mig_{filename[:12]}", _VERSIONS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load("a3c8e1f5b7d2_index_scheduled_test_configurations.py")


@pytest.fixture
def conn(admin_test_db):
    connection = admin_test_db.connection()
    with Operations.context(MigrationContext.configure(connection)):
        yield connection


def _definition(conn) -> str | None:
    return conn.execute(
        sa.text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"), {"name": _INDEX}
    ).scalar()


def test_head_has_the_partial_index(conn):
    definition = _definition(conn)
    assert definition is not None
    assert "'schedule'" in definition
    assert "deleted_at IS NULL" in definition


def test_round_trip(conn):
    _migration.downgrade()
    assert _definition(conn) is None
    _migration.upgrade()
    _migration.upgrade()  # IF NOT EXISTS
    assert _definition(conn) is not None
