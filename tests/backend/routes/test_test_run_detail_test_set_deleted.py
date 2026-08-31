"""GET /test_runs/{id} exposes test_configuration.test_set.deleted_at.

The eager-loaded `test_configuration -> test_set` join doesn't apply the
soft-delete filter, so a soft-deleted test set still comes through with
`deleted_at` set. The frontend reads this field directly to decide whether
to enable the Re-run FAB, instead of firing a second `GET /test_sets/{id}`.
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from tests.backend.fixtures.test_setup import create_test_organization_and_user


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _make_run_with_test_set(db: Session, org, user) -> tuple[models.TestRun, models.TestSet]:
    project = models.Project(
        name="Test Set Deleted Project",
        organization_id=org.id,
        user_id=user.id,
    )
    db.add(project)
    db.flush()

    endpoint = models.Endpoint(
        name="Test Set Deleted Endpoint",
        connection_type="REST",
        url="https://api.example.com/test",
        method="POST",
        organization_id=org.id,
        user_id=user.id,
        project_id=project.id,
    )
    db.add(endpoint)
    db.flush()

    test_set = models.TestSet(name="Deletable Test Set", organization_id=org.id, user_id=user.id)
    db.add(test_set)
    db.flush()

    test_config = models.TestConfiguration(
        endpoint_id=endpoint.id,
        test_set_id=test_set.id,
        organization_id=org.id,
        user_id=user.id,
    )
    db.add(test_config)
    db.flush()

    status = models.Status(name="Progress", organization_id=org.id, user_id=user.id)
    db.add(status)
    db.flush()

    test_run = models.TestRun(
        name="Test Set Deleted Run",
        user_id=user.id,
        organization_id=org.id,
        status_id=status.id,
        test_configuration_id=test_config.id,
    )
    db.add(test_run)
    db.commit()
    db.refresh(test_run)
    db.refresh(test_set)
    return test_run, test_set


class TestTestRunDetailExposesTestSetDeletion:
    def test_deleted_at_is_null_for_a_live_test_set(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Test Set Deleted Org", "owner@test-set-deleted.com", "Owner"
        )
        test_run, _test_set = _make_run_with_test_set(test_db, org, user)

        response = client.get(f"/test_runs/{test_run.id}", headers=_auth(token))

        assert response.status_code == 200
        assert response.json()["test_configuration"]["test_set"]["deleted_at"] is None

    def test_deleted_at_is_set_once_the_test_set_is_soft_deleted(
        self, client: TestClient, test_db: Session
    ):
        org, user, token = create_test_organization_and_user(
            test_db, "Test Set Deleted Org 2", "owner2@test-set-deleted.com", "Owner"
        )
        test_run, test_set = _make_run_with_test_set(test_db, org, user)

        # Soft-delete the test set directly -- exercising the real DELETE route isn't
        # the point of this test, only that the join surfaces whatever deleted_at holds.
        test_db.query(models.TestSet).filter(models.TestSet.id == test_set.id).update(
            {"deleted_at": datetime.now(timezone.utc)}
        )
        test_db.commit()

        response = client.get(f"/test_runs/{test_run.id}", headers=_auth(token))

        assert response.status_code == 200
        assert response.json()["test_configuration"]["test_set"]["deleted_at"] is not None
