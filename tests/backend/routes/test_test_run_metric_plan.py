"""Test-run responses leave out ``attributes.metric_plan``, and updates keep it."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from tests.backend.fixtures.test_setup import create_test_organization_and_user
from tests.backend.routes.test_test_run_detail_test_set_deleted import (
    _auth,
    _make_run_with_test_set,
)

PLAN = {"metric_backends": ["sdk"], "has_multi_turn": False, "test_order": ["t1"]}


def _run_with_plan(db: Session, label: str):
    org, user, token = create_test_organization_and_user(
        db, f"Metric Plan Org {label}", f"owner@metric-plan-{label}.com", "Owner"
    )
    test_run, _ = _make_run_with_test_set(db, org, user)
    test_run.attributes = {"task_id": "task-1", "metric_plan": PLAN}
    db.commit()
    return test_run, token


class TestTestRunResponsesLeaveOutMetricPlan:
    def test_detail_and_list(self, client: TestClient, test_db: Session):
        test_run, token = _run_with_plan(test_db, "read")

        detail = client.get(f"/test_runs/{test_run.id}", headers=_auth(token))
        listed = client.get("/test_runs/", headers=_auth(token))

        assert detail.status_code == 200
        assert detail.json()["attributes"] == {"task_id": "task-1"}
        assert listed.status_code == 200
        [item] = [run for run in listed.json() if run["id"] == str(test_run.id)]
        assert item["attributes"] == {"task_id": "task-1"}

    def test_update_with_attributes_keeps_the_stored_plan(
        self, client: TestClient, test_db: Session
    ):
        test_run, token = _run_with_plan(test_db, "update")

        response = client.put(
            f"/test_runs/{test_run.id}",
            json={"attributes": {"task_id": "task-1", "note": "x"}},
            headers=_auth(token),
        )

        assert response.status_code == 200
        assert response.json()["attributes"] == {"task_id": "task-1", "note": "x"}
        test_db.expire_all()
        stored = test_db.get(models.TestRun, test_run.id).attributes
        assert stored == {"task_id": "task-1", "note": "x", "metric_plan": PLAN}
