"""`$select` on the run list skips the aggregates it would drop anyway."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.backend.fixtures.test_setup import create_test_organization_and_user
from tests.backend.routes.test_test_run_detail_test_set_deleted import (
    _auth,
    _make_run_with_test_set,
)

_PROCESSOR = "rhesis.backend.jobs.execution.result_processor"
_ANNOTATIONS = "rhesis.backend.app.crud.annotation.get_annotation_statistics_for_runs"
_USAGE = "rhesis.backend.app.crud.test_run.get_usage_statistics_for_runs"


def _setup(db: Session, label: str):
    org, user, token = create_test_organization_and_user(
        db, f"Run Select Org {label}", f"owner@run-select-{label}.com", "Owner"
    )
    test_run, _ = _make_run_with_test_set(db, org, user)
    return test_run, token


def test_selecting_plain_fields_skips_the_aggregates(client: TestClient, test_db: Session):
    test_run, token = _setup(test_db, "plain")
    boom = AssertionError("aggregate computed for a field nobody selected")

    with (
        patch(f"{_PROCESSOR}.get_test_statistics_for_runs", side_effect=boom),
        patch(_ANNOTATIONS, side_effect=boom),
        patch(_USAGE, side_effect=boom),
    ):
        response = client.get("/test_runs/?$select=id,name", headers=_auth(token))

    assert response.status_code == 200
    [item] = [run for run in response.json() if run["id"] == str(test_run.id)]
    assert set(item) == {"id", "name"}


def test_a_full_list_still_carries_stats_and_usage(client: TestClient, test_db: Session):
    test_run, token = _setup(test_db, "full")

    response = client.get("/test_runs/", headers=_auth(token))

    [item] = [run for run in response.json() if run["id"] == str(test_run.id)]
    assert item["stats"] == {"total": 0, "passed": 0, "failed": 0, "errors": 0}
    assert "usage" in item


def test_selecting_stats_still_computes_them(client: TestClient, test_db: Session):
    test_run, token = _setup(test_db, "stats")

    response = client.get("/test_runs/?$select=id,stats", headers=_auth(token))

    [item] = [run for run in response.json() if run["id"] == str(test_run.id)]
    assert item == {
        "id": str(test_run.id),
        "stats": {"total": 0, "passed": 0, "failed": 0, "errors": 0},
    }
