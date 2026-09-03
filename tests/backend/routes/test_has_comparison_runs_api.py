"""GET /test_runs/{id}/has-comparison-runs -- tenant boundary and existence semantics.

This route backs the test run detail page's Compare FAB: it answers "does any
other test run exist on this test set" with a single EXISTS query, replacing a
client-side fetch through the paginated test run list endpoint.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from tests.backend.fixtures.test_setup import create_test_organization_and_user


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _make_run(db: Session, org, user, test_set=None) -> models.TestRun:
    project = models.Project(
        name="Comparison Runs Project",
        organization_id=org.id,
        user_id=user.id,
    )
    db.add(project)
    db.flush()

    endpoint = models.Endpoint(
        name="Comparison Runs Endpoint",
        connection_type="REST",
        url="https://api.example.com/test",
        method="POST",
        organization_id=org.id,
        user_id=user.id,
        project_id=project.id,
    )
    db.add(endpoint)
    db.flush()

    test_config = models.TestConfiguration(
        endpoint_id=endpoint.id,
        test_set_id=test_set.id if test_set else None,
        organization_id=org.id,
        user_id=user.id,
    )
    db.add(test_config)
    db.flush()

    status = models.Status(name="Progress", organization_id=org.id, user_id=user.id)
    db.add(status)
    db.flush()

    test_run = models.TestRun(
        name="Comparison Runs Run",
        user_id=user.id,
        organization_id=org.id,
        status_id=status.id,
        test_configuration_id=test_config.id,
    )
    db.add(test_run)
    db.commit()
    db.refresh(test_run)
    return test_run


def _make_test_set(db: Session, org, user) -> models.TestSet:
    test_set = models.TestSet(
        name="Comparison Runs Test Set", organization_id=org.id, user_id=user.id
    )
    db.add(test_set)
    db.commit()
    db.refresh(test_set)
    return test_set


class TestHasComparisonRunsEndpoint:
    def test_false_when_no_sibling_run_exists(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Comparison Runs Org", "owner@comparison-runs.com", "Owner"
        )
        test_set = _make_test_set(test_db, org, user)
        test_run = _make_run(test_db, org, user, test_set=test_set)

        response = client.get(
            f"/test_runs/{test_run.id}/has-comparison-runs?test_set_id={test_set.id}",
            headers=_auth(token),
        )

        assert response.status_code == 200
        assert response.json() == {"has_comparison_runs": False}

    def test_true_when_a_sibling_run_exists(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Comparison Runs Org 2", "owner2@comparison-runs.com", "Owner"
        )
        test_set = _make_test_set(test_db, org, user)
        test_run = _make_run(test_db, org, user, test_set=test_set)
        _make_run(test_db, org, user, test_set=test_set)

        response = client.get(
            f"/test_runs/{test_run.id}/has-comparison-runs?test_set_id={test_set.id}",
            headers=_auth(token),
        )

        assert response.status_code == 200
        assert response.json() == {"has_comparison_runs": True}

    def test_other_organizations_runs_never_count(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Comparison Runs Org 3", "owner3@comparison-runs.com", "Owner"
        )
        test_set = _make_test_set(test_db, org, user)
        test_run = _make_run(test_db, org, user, test_set=test_set)

        other_org, other_user, _ = create_test_organization_and_user(
            test_db, "Comparison Runs Other Org", "other@comparison-runs.com", "Other"
        )
        other_test_set = _make_test_set(test_db, other_org, other_user)
        _make_run(test_db, other_org, other_user, test_set=other_test_set)

        response = client.get(
            f"/test_runs/{test_run.id}/has-comparison-runs?test_set_id={test_set.id}",
            headers=_auth(token),
        )

        assert response.status_code == 200
        assert response.json() == {"has_comparison_runs": False}

    def test_requires_test_set_id(self, client: TestClient, test_db: Session):
        _, _, token = create_test_organization_and_user(
            test_db, "Comparison Runs Org 4", "owner4@comparison-runs.com", "Owner"
        )
        response = client.get(
            "/test_runs/00000000-0000-0000-0000-000000000000/has-comparison-runs",
            headers=_auth(token),
        )
        assert response.status_code == 422
