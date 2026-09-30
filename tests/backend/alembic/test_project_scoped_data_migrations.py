"""Org-by-org data migrations under an RLS-enforced role.

01926b6dd2b6 and 8c1f4e2a7b9d bind the org GUC and leave ``app.current_project``
blank. The restrictive ``project_isolation`` policy then only shows rows with a
NULL ``project_id``, so a role without BYPASSRLS skips every project row. The
test suite runs as such a role (``rhesis-app``). 17eb2c93d8e0 re-runs both
rewrites once per project.
"""

import importlib.util
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

from rhesis.backend.app import models
from tests.backend.fixtures.rls import TEST_GUC_KEY, scope_to_org, scope_to_project

RHESIS_SKIP_MIGRATIONS = os.environ.get("RHESIS_SKIP_MIGRATIONS", "").lower() in (
    "1",
    "true",
    "yes",
)

pytestmark = pytest.mark.skipif(
    RHESIS_SKIP_MIGRATIONS,
    reason="Depends on the head schema; skipped when RHESIS_SKIP_MIGRATIONS is set.",
)

_VERSIONS = (
    Path(__file__).parent.parent.parent.parent
    / "apps"
    / "backend"
    / "src"
    / "rhesis"
    / "backend"
    / "alembic"
    / "versions"
)


def _load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _VERSIONS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_override_marker = _load("01926b6dd2b6_rename_override_marker_key.py", "rls_repro_01926b6dd2b6")
_goal_criteria = _load(
    "8c1f4e2a7b9d_rename_goal_behaviours_to_criteria.py", "rls_repro_8c1f4e2a7b9d"
)
_rerun = _load("17eb2c93d8e0_rerun_json_key_renames_per_project.py", "rls_fix_17eb2c93d8e0")

_MARKER_METRICS = {
    "metrics": {
        "M": {
            "is_successful": False,
            "override": {"original_value": True, "review_id": str(uuid.uuid4())},
        }
    }
}

_GOAL_OUTPUT = {
    "goal_evaluation": {
        "contract": {"required_behavior": ["Refuse"]},
        "behavior_verdicts": [{"behavior": "Refuse", "kind": "required", "complied": True}],
        "behaviors_total": 1,
    }
}


@pytest.fixture
def migration_ops(test_db):
    ctx = MigrationContext.configure(test_db.connection())
    with Operations.context(ctx):
        yield


@pytest.fixture
def project_id(test_db, test_org_id, authenticated_user_id):
    project = models.Project(
        name=f"RLS migration {uuid.uuid4().hex[:8]}",
        organization_id=test_org_id,
        user_id=authenticated_user_id,
    )
    test_db.add(project)
    test_db.flush()
    return str(project.id)


def _insert_result(conn, *, org_id, user_id, project_id=None, metrics=None, output=None):
    return conn.execute(
        sa.text(
            """
            INSERT INTO test_result
                (organization_id, user_id, project_id, test_metrics, test_output)
            VALUES (
                CAST(:org_id AS uuid), CAST(:user_id AS uuid), CAST(:project_id AS uuid),
                CAST(:metrics AS jsonb), CAST(:output AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "org_id": org_id,
            "user_id": user_id,
            "project_id": project_id,
            "metrics": None if metrics is None else json.dumps(metrics),
            "output": None if output is None else json.dumps(output),
        },
    ).scalar()


def _rebind(test_db, project_id):
    # The migrations leave the GUCs on whichever scope they walked last.
    scope_to_org(test_db, test_db.info[TEST_GUC_KEY]["org_id"])
    scope_to_project(test_db, project_id)


def _read(test_db, project_id, column, result_id):
    _rebind(test_db, project_id)
    raw = (
        test_db.connection()
        .execute(
            sa.text(f"SELECT {column} FROM test_result WHERE id = :id"),  # noqa: S608
            {"id": result_id},
        )
        .scalar()
    )
    return json.loads(raw) if isinstance(raw, str) else raw


def _seed(test_db, test_org_id, user_id, project_id, **payload):
    conn = test_db.connection()
    scoped = None
    if project_id:
        scope_to_project(test_db, project_id)
        scoped = _insert_result(
            conn, org_id=test_org_id, user_id=user_id, project_id=project_id, **payload
        )
    scope_to_project(test_db, None)
    unscoped = _insert_result(conn, org_id=test_org_id, user_id=user_id, **payload)
    return scoped, unscoped


def _override(test_db, project_id, result_id):
    return _read(test_db, project_id, "test_metrics", result_id)["metrics"]["M"]["override"]


def _insert_trace(conn, *, org_id, project_id, trace_metrics) -> uuid.UUID:
    now = datetime.now(timezone.utc)
    return conn.execute(
        sa.text(
            """
            INSERT INTO trace (
                trace_id, span_id, project_id, organization_id, environment,
                span_name, span_kind, start_time, end_time, duration_ms,
                status_code, attributes, events, links, resource, trace_metrics
            )
            VALUES (
                :trace_id, :span_id, CAST(:project_id AS uuid), CAST(:org_id AS uuid),
                'development', 'function.test', 'INTERNAL', :start, :end, 1.0,
                'OK', '{}', '[]', '[]', '{}', CAST(:metrics AS jsonb)
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
            "metrics": json.dumps(trace_metrics),
        },
    ).scalar()


@pytest.mark.integration
class TestRerunReachesProjectRows:
    def _seed_all(self, test_db, test_org_id, user_id, project_id):
        payload = {"metrics": _MARKER_METRICS, "output": _GOAL_OUTPUT}
        scoped, unscoped = _seed(test_db, test_org_id, user_id, project_id, **payload)
        scope_to_project(test_db, project_id)
        trace = _insert_trace(
            test_db.connection(),
            org_id=test_org_id,
            project_id=project_id,
            trace_metrics={"turn_overrides": {"1": {"override": {"review_id": "x"}}}},
        )
        scope_to_project(test_db, None)
        return scoped, unscoped, trace

    def _trace_override(self, test_db, project_id, trace_id):
        _rebind(test_db, project_id)
        raw = (
            test_db.connection()
            .execute(sa.text("SELECT trace_metrics FROM trace WHERE id = :id"), {"id": trace_id})
            .scalar()
        )
        return raw["turn_overrides"]["1"]["override"]

    def _assert_rewritten(self, test_db, project_id, result_id):
        override = _override(test_db, project_id, result_id)
        assert "annotation_id" in override and "review_id" not in override
        goal = _read(test_db, project_id, "test_output", result_id)["goal_evaluation"]
        assert goal["criteria_total"] == 1
        assert goal["contract"] == {"required_criteria": ["Refuse"]}
        assert goal["criteria_evaluations"][0]["criterion"] == "Refuse"

    def test_rewrites_project_rows_the_originals_missed(
        self, test_db, migration_ops, test_org_id, authenticated_user_id, project_id
    ):
        scoped, unscoped, trace = self._seed_all(
            test_db, test_org_id, authenticated_user_id, project_id
        )
        _override_marker.upgrade()
        _goal_criteria.upgrade()

        _rerun.upgrade()

        self._assert_rewritten(test_db, project_id, scoped)
        self._assert_rewritten(test_db, project_id, unscoped)
        assert self._trace_override(test_db, project_id, trace) == {"annotation_id": "x"}

    def test_is_idempotent(
        self, test_db, migration_ops, test_org_id, authenticated_user_id, project_id
    ):
        scoped, unscoped, trace = self._seed_all(
            test_db, test_org_id, authenticated_user_id, project_id
        )

        _rerun.upgrade()
        first = [
            _read(test_db, project_id, c, r)
            for r in (scoped, unscoped)
            for c in ("test_metrics", "test_output")
        ]
        _rerun.upgrade()
        second = [
            _read(test_db, project_id, c, r)
            for r in (scoped, unscoped)
            for c in ("test_metrics", "test_output")
        ]

        assert first == second
        self._assert_rewritten(test_db, project_id, scoped)
        assert self._trace_override(test_db, project_id, trace) == {"annotation_id": "x"}
