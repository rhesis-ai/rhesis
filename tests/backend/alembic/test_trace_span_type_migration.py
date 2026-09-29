"""Tests for the trace.span_type migration.

The SQL version of the span-type rule must agree with classify_span_type on
every case in SPAN_TYPE_CASES, and the batched backfill must reach every row.

Runs on ``admin_test_db`` (superuser, so RLS doesn't filter the UPDATE) and
calls the backfill helpers directly: upgrade() itself commits in autocommit
blocks, which would escape the test's rollback.
"""

import importlib.util
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

from rhesis.backend.app.services.telemetry.span_types import classify_span_type
from tests.backend.services.telemetry.test_span_types import SPAN_TYPE_CASES

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
    / "e3b7a1c4d9f2_add_trace_span_type.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("span_type_migration_under_test", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()


def _sql_span_type(conn, attributes) -> str:
    return conn.execute(
        sa.text(
            f"SELECT {_migration._SPAN_TYPE_SQL} "  # noqa: S608
            "FROM (SELECT CAST(:attrs AS jsonb) AS attributes) t"
        ),
        {"attrs": json.dumps(attributes)},
    ).scalar()


@pytest.mark.integration
@pytest.mark.parametrize(
    "attributes,expected",
    [(attrs, expected) for _, attrs, expected in SPAN_TYPE_CASES],
    ids=[case_id for case_id, _, _ in SPAN_TYPE_CASES],
)
def test_sql_rule_matches_python_rule(admin_test_db, attributes, expected):
    sql_type = _sql_span_type(admin_test_db.connection(), attributes)

    assert sql_type == classify_span_type(attributes) == expected


@pytest.fixture
def project_id(admin_test_db, test_org_id, authenticated_user_id):
    return (
        admin_test_db.connection()
        .execute(
            sa.text(
                "INSERT INTO project (name, organization_id, user_id) "
                "VALUES (:name, CAST(:org AS uuid), CAST(:user AS uuid)) RETURNING id"
            ),
            {
                "name": f"span_type migration {uuid.uuid4().hex[:8]}",
                "org": test_org_id,
                "user": authenticated_user_id,
            },
        )
        .scalar()
    )


def _insert_trace(conn, *, project_id, org_id, attributes) -> uuid.UUID:
    now = datetime.now(timezone.utc)
    return conn.execute(
        sa.text(
            """
            INSERT INTO trace (
                trace_id, span_id, project_id, organization_id, environment,
                span_name, span_kind, start_time, end_time, duration_ms,
                status_code, attributes, events, links, resource
            )
            VALUES (
                :trace_id, :span_id, CAST(:project_id AS uuid), CAST(:org_id AS uuid),
                'development', 'function.test', 'INTERNAL', :start, :end, 1.0,
                'OK', CAST(:attrs AS jsonb), '[]', '[]', '{}'
            )
            RETURNING id
            """
        ),
        {
            "trace_id": uuid.uuid4().hex,
            "span_id": uuid.uuid4().hex[:16],
            "project_id": project_id,
            "org_id": org_id,
            "start": now,
            "end": now + timedelta(milliseconds=1),
            "attrs": json.dumps(attributes),
        },
    ).scalar()


def _span_types(conn, ids) -> dict:
    rows = conn.execute(
        sa.text("SELECT id, span_type FROM trace WHERE id = ANY(:ids)"),
        {"ids": list(ids)},
    ).fetchall()
    return {row.id: row.span_type for row in rows}


@pytest.fixture
def seeded_traces(admin_test_db, project_id, test_org_id):
    """One trace row per shared case, all reset to the column default."""
    conn = admin_test_db.connection()
    expected = {
        _insert_trace(conn, project_id=project_id, org_id=test_org_id, attributes=attrs): want
        for _, attrs, want in SPAN_TYPE_CASES
    }
    conn.execute(
        sa.text("UPDATE trace SET span_type = 'span' WHERE id = ANY(:ids)"),
        {"ids": list(expected)},
    )
    return expected


@pytest.mark.integration
class TestBackfill:
    def test_batched_backfill_types_every_row(self, admin_test_db, seeded_traces):
        conn = admin_test_db.connection()

        # A batch size far below the row count forces many keyset batches.
        _migration._backfill(conn, batch_size=2)

        assert _span_types(conn, seeded_traces) == seeded_traces

    def test_backfill_is_a_no_op_when_rerun(self, admin_test_db, seeded_traces):
        conn = admin_test_db.connection()
        _migration._backfill(conn, batch_size=3)

        assert _migration._backfill(conn, batch_size=3) == 0

    def test_backfill_under_rls_restores_rls(self, admin_test_db, seeded_traces):
        conn = admin_test_db.connection()

        _migration._backfill_under_rls(conn)

        assert _span_types(conn, seeded_traces) == seeded_traces
        assert conn.execute(
            sa.text("SELECT relrowsecurity FROM pg_class WHERE relname = 'trace'")
        ).scalar()


@pytest.mark.integration
def test_span_type_index_exists(admin_test_db):
    columns = (
        admin_test_db.connection()
        .execute(
            sa.text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"),
            {"name": _migration._INDEX},
        )
        .scalar()
    )

    assert columns is not None
    assert "(project_id, span_type, start_time DESC)" in columns
