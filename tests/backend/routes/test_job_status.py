"""HTTP-level tenant check for the job status endpoints.

Regression test for the IDOR in ``GET /jobs/{task_id}``: before this fix, any
authenticated user could read any Celery task's status regardless of which
organization dispatched it. The fix proves ownership via a ``TestRun`` row
recording the task id, on a tenant-scoped session -- see
``app/routers/job.py`` for why this is a stopgap rather than the final shape.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/routes/test_job_status.py -v
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from tests.backend.fixtures.test_setup import create_test_organization_and_user
from tests.backend.routes.fixtures.data_factories import EndpointDataFactory


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _create_test_run_with_task_id(
    test_db: Session, organization, user, task_id: str
) -> models.TestRun:
    """Build the minimal project -> endpoint -> test_configuration -> test_run
    chain needed to record a Celery task id somewhere queryable, absent a
    ``job`` table.
    """
    project = models.Project(
        name="Job Status Test Project",
        organization_id=organization.id,
        user_id=user.id,
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)

    endpoint_data = EndpointDataFactory.minimal_data()
    endpoint_data["project_id"] = str(project.id)
    endpoint = crud.create_endpoint(
        db=test_db,
        endpoint=endpoint_data,
        organization_id=str(organization.id),
        user_id=str(user.id),
    )

    test_config = models.TestConfiguration(
        id=uuid.uuid4(),
        endpoint_id=endpoint.id,
        organization_id=organization.id,
        user_id=user.id,
    )
    test_db.add(test_config)
    test_db.commit()

    test_run = models.TestRun(
        id=uuid.uuid4(),
        organization_id=organization.id,
        user_id=user.id,
        name="Job status test run",
        test_configuration_id=test_config.id,
        attributes={"task_id": task_id},
    )
    test_db.add(test_run)
    test_db.commit()
    return test_run


@pytest.mark.security
class TestJobStatusTenantCheck:
    """GET /jobs/by-celery-id/{id} and its deprecated GET /jobs/{id} alias."""

    def test_owner_can_read_own_task_status(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Job Status Org", "owner@job-status-test.com", "Job Status Owner"
        )
        task_id = str(uuid.uuid4())
        _create_test_run_with_task_id(test_db, org, user, task_id)

        response = client.get(f"/jobs/by-celery-id/{task_id}", headers=_auth(token))

        assert response.status_code == 200
        body = response.json()
        assert body["task_id"] == task_id
        assert "status" in body

    def test_other_organization_cannot_read_task_status(self, client: TestClient, test_db: Session):
        """SECURITY: the fixed IDOR. Org B must not see Org A's task by id."""
        org_a, user_a, _ = create_test_organization_and_user(
            test_db, "Job Status Org A", "usera@job-status-test.com", "User A"
        )
        task_id = str(uuid.uuid4())
        _create_test_run_with_task_id(test_db, org_a, user_a, task_id)

        _, _, token_b = create_test_organization_and_user(
            test_db, "Job Status Org B", "userb@job-status-test.com", "User B"
        )

        response = client.get(f"/jobs/by-celery-id/{task_id}", headers=_auth(token_b))

        assert response.status_code == 404

    def test_unknown_task_id_is_404(self, client: TestClient, test_db: Session):
        _, _, token = create_test_organization_and_user(
            test_db, "Job Status Org Unknown", "unknown@job-status-test.com", "User"
        )

        response = client.get(f"/jobs/by-celery-id/{uuid.uuid4()}", headers=_auth(token))

        assert response.status_code == 404

    def test_deprecated_alias_enforces_the_same_tenant_check(
        self, client: TestClient, test_db: Session
    ):
        org_a, user_a, _ = create_test_organization_and_user(
            test_db, "Job Status Org Alias A", "aliasa@job-status-test.com", "User A"
        )
        task_id = str(uuid.uuid4())
        _create_test_run_with_task_id(test_db, org_a, user_a, task_id)

        _, _, token_b = create_test_organization_and_user(
            test_db, "Job Status Org Alias B", "aliasb@job-status-test.com", "User B"
        )

        owner_response = client.get(f"/jobs/{task_id}", headers=_auth(token_b))
        assert owner_response.status_code == 404

    def test_deprecated_alias_marked_deprecated_in_openapi(self, client: TestClient):
        schema = client.get("/openapi.json").json()
        get_op = schema["paths"]["/jobs/{task_id}"]["get"]
        assert get_op.get("deprecated") is True
