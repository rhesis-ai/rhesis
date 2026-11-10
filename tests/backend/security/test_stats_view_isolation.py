"""Stats views must never count or label one organization's rows with another's.

Org A writes a test_result that points at org B's test. B's v_test_stats row
for that test must not count it, and A's v_test_result_stats / v_metric_stats
must not join B's test into A's row. Checked twice:

- as the superuser (bypasses RLS, like the view owner in prd and the self-host
  app role), which only the organization match in the views' joins stops;
- as the app role scoped to org B, which RLS stops once the views run as the
  caller (security_invoker).
"""

import json
import uuid
from contextlib import contextmanager

import pytest
from sqlalchemy import text

APP_ROLE = "rhesis-app"


def _insert(db, table: str, **values) -> uuid.UUID:
    values.setdefault("id", uuid.uuid4())
    cols = ", ".join(f'"{c}"' for c in values)
    params = ", ".join(f":{c}" for c in values)
    db.execute(text(f'INSERT INTO "{table}" ({cols}) VALUES ({params})'), values)
    return values["id"]


def _org_with_status(db, label: str) -> tuple[uuid.UUID, uuid.UUID]:
    org_id = _insert(db, "organization", name=f"stats-view-{label}-{uuid.uuid4().hex[:8]}")
    status_id = _insert(db, "status", name="Pass", organization_id=org_id)
    return org_id, status_id


def _result(db, org_id, status_id, test_id) -> uuid.UUID:
    metrics = {"metrics": {"Accuracy": {"is_successful": True, "score": 1.0}}}
    return _insert(
        db,
        "test_result",
        organization_id=org_id,
        status_id=status_id,
        test_id=test_id,
        execution="ok",
        verdict="pass",
        test_metrics=json.dumps(metrics),
    )


@pytest.fixture
def cross_org_rows(admin_test_db):
    """B owns a test with one result; A adds a result pointing at B's test."""
    db = admin_test_db
    org_a, status_a = _org_with_status(db, "a")
    org_b, status_b = _org_with_status(db, "b")
    topic_b = _insert(db, "topic", name="org-b-private-topic", organization_id=org_b)
    test_b = _insert(db, "test", organization_id=org_b, topic_id=topic_b)
    _result(db, org_b, status_b, test_b)
    foreign_result = _result(db, org_a, status_a, test_b)
    db.flush()
    return {"org_a": org_a, "org_b": org_b, "test_b": test_b, "foreign_result": foreign_result}


@contextmanager
def _as_app_role(db, organization_id):
    """Run as the NOBYPASSRLS app role with the request GUCs of one org."""
    db.execute(text(f'SET ROLE "{APP_ROLE}"'))
    db.execute(
        text(
            "SELECT set_config('app.current_organization', :org, true),"
            " set_config('app.current_project', '', true)"
        ),
        {"org": str(organization_id)},
    )
    try:
        yield
    finally:
        db.execute(text("RESET ROLE"))


def _test_stats(db, test_id, org_id):
    return db.execute(
        text(
            "SELECT run_count, passed_count FROM v_test_stats"
            " WHERE test_id = :t AND organization_id = :o"
        ),
        {"t": test_id, "o": org_id},
    ).one()


def _rows_for_result(db, view: str, result_id) -> int:
    return db.execute(
        text(f"SELECT count(*) FROM {view} WHERE test_result_id = :r"), {"r": result_id}
    ).scalar_one()


@pytest.mark.security
class TestStatsViewIsolation:
    def test_foreign_result_not_counted_for_bypassrls_role(self, admin_test_db, cross_org_rows):
        run_count, passed_count = _test_stats(
            admin_test_db, cross_org_rows["test_b"], cross_org_rows["org_b"]
        )
        assert (run_count, passed_count) == (1, 1)

    def test_foreign_result_not_counted_for_app_role(self, admin_test_db, cross_org_rows):
        with _as_app_role(admin_test_db, cross_org_rows["org_b"]):
            run_count, passed_count = _test_stats(
                admin_test_db, cross_org_rows["test_b"], cross_org_rows["org_b"]
            )
        assert (run_count, passed_count) == (1, 1)

    @pytest.mark.parametrize("view", ["v_test_result_stats", "v_metric_stats"])
    def test_foreign_test_not_joined_into_result_rows(self, admin_test_db, cross_org_rows, view):
        """A's result must not pick up B's test (and its topic name) through the join."""
        foreign = cross_org_rows["foreign_result"]
        assert _rows_for_result(admin_test_db, view, foreign) == 0
        with _as_app_role(admin_test_db, cross_org_rows["org_a"]):
            assert _rows_for_result(admin_test_db, view, foreign) == 0
