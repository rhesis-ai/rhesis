"""GET /test_runs/{id}/verdict-matrix -- tenant boundary and shape.

Encoding correctness (cell alphabet, KPIs, plan/fallback paths) is covered
at the service layer in tests/backend/services/test_verdict_matrix.py; this
file only checks the route wires auth, 404s, and the columns=none param.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from tests.backend.fixtures.test_setup import create_test_organization_and_user


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _make_run(db: Session, org, user) -> models.TestRun:
    project = models.Project(
        name="Verdict Matrix Project",
        organization_id=org.id,
        user_id=user.id,
    )
    db.add(project)
    db.flush()

    endpoint = models.Endpoint(
        name="Verdict Matrix Endpoint",
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
        organization_id=org.id,
        user_id=user.id,
    )
    db.add(test_config)
    db.flush()

    status = models.Status(name="Progress", organization_id=org.id, user_id=user.id)
    db.add(status)
    db.flush()

    test_run = models.TestRun(
        name="Verdict Matrix Route Run",
        user_id=user.id,
        organization_id=org.id,
        status_id=status.id,
        test_configuration_id=test_config.id,
    )
    db.add(test_run)
    db.commit()
    db.refresh(test_run)
    return test_run


class TestVerdictMatrixEndpoint:
    def test_returns_matrix_shape_for_own_run(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Verdict Matrix Org", "owner@verdict-matrix.com", "Owner"
        )
        test_run = _make_run(test_db, org, user)

        response = client.get(f"/test_runs/{test_run.id}/verdict-matrix", headers=_auth(token))

        assert response.status_code == 200
        body = response.json()
        assert body["test_run_id"] == str(test_run.id)
        assert body["rows"] == []
        assert body["requirements"] == []
        assert body["kpis"]["tests_total"] == 0

    def test_columns_none_omits_test_ids(self, client: TestClient, test_db: Session):
        org, user, token = create_test_organization_and_user(
            test_db, "Verdict Matrix Org 2", "owner2@verdict-matrix.com", "Owner"
        )
        test_run = _make_run(test_db, org, user)

        response = client.get(
            f"/test_runs/{test_run.id}/verdict-matrix?columns=none", headers=_auth(token)
        )

        assert response.status_code == 200
        assert response.json()["test_ids"] is None

    def test_other_organization_gets_404(self, client: TestClient, test_db: Session):
        owner_org, owner_user, _ = create_test_organization_and_user(
            test_db, "Verdict Matrix Owner Org", "owner3@verdict-matrix.com", "Owner"
        )
        test_run = _make_run(test_db, owner_org, owner_user)

        _, _, other_token = create_test_organization_and_user(
            test_db, "Verdict Matrix Other Org", "other@verdict-matrix.com", "Other"
        )

        response = client.get(
            f"/test_runs/{test_run.id}/verdict-matrix", headers=_auth(other_token)
        )

        assert response.status_code == 404

    def test_unknown_run_is_404(self, client: TestClient, test_db: Session):
        _, _, token = create_test_organization_and_user(
            test_db, "Verdict Matrix Org 4", "owner4@verdict-matrix.com", "Owner"
        )
        response = client.get(
            "/test_runs/00000000-0000-0000-0000-000000000000/verdict-matrix",
            headers=_auth(token),
        )
        assert response.status_code == 404
