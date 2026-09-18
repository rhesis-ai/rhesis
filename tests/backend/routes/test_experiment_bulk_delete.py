"""Tests for DELETE /experiments/bulk endpoint.

Registered before /{experiment_id} in routers/experiments.py. Guards:
- owner-only delete rule (only the creator may delete their experiment)
- environment unbind pre-pass (matching single-delete behaviour)
- route ordering (FastAPI must not swallow "bulk" as an experiment_id)
"""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.models.experiment import Experiment


def _experiments_url(project_id) -> str:
    return f"/projects/{project_id}/experiments"


def _schema_url(project_id) -> str:
    return f"/projects/{project_id}/parameters/schema"


def _versions_url(experiment_id) -> str:
    return f"/experiments/{experiment_id}/versions"


def _environment_url(project_id, name) -> str:
    return f"/projects/{project_id}/parameters/environments/{name}"


def _environments_url(project_id) -> str:
    return f"/projects/{project_id}/parameters/environments"


def _seed_schema(client: TestClient, project_id) -> None:
    payload = {
        "fields": [
            {
                "name": "temperature",
                "type": "number",
                "required": False,
                "default": {"type": "number", "value": 0.7},
            },
        ]
    }
    response = client.put(_schema_url(project_id), json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text


def _create_experiment(
    client: TestClient,
    project_id,
    *,
    name: str = "baseline",
    visibility: str = "private",
) -> dict:
    response = client.post(
        _experiments_url(project_id),
        json={"name": name, "description": "test", "visibility": visibility},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


@pytest.mark.integration
class TestBulkDeleteExperimentsEndpoint:
    """Tests for DELETE /experiments/bulk"""

    def test_bulk_delete_owned_experiment(
        self,
        authenticated_client: TestClient,
        db_project,
    ):
        exp = _create_experiment(authenticated_client, db_project.id)

        response = authenticated_client.request(
            "DELETE",
            "/experiments/bulk",
            json={"experiment_ids": [exp["id"]]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == [exp["id"]]
        assert data["not_found_ids"] == []
        assert data["forbidden_ids"] == []

    def test_bulk_delete_not_found_ids(
        self,
        authenticated_client: TestClient,
        db_project,
    ):
        fake_id = str(uuid.uuid4())

        response = authenticated_client.request(
            "DELETE",
            "/experiments/bulk",
            json={"experiment_ids": [fake_id]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == []
        assert data["not_found_ids"] == [fake_id]
        assert data["forbidden_ids"] == []

    def test_bulk_delete_forbidden_experiment_not_deleted(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        db_project,
        db_user,
    ):
        """A shared experiment owned by a different user is reported as
        forbidden, not silently deleted. Must be shared so the visibility
        filter lets the caller see it (private would land in not_found)."""
        other_experiment = Experiment(
            name="Other user's experiment",
            owner_user_id=db_user.id,
            visibility="shared",
            project_id=db_project.id,
            organization_id=db_project.organization_id,
        )
        test_db.add(other_experiment)
        test_db.flush()
        test_db.refresh(other_experiment)

        response = authenticated_client.request(
            "DELETE",
            "/experiments/bulk",
            json={"experiment_ids": [str(other_experiment.id)]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == []
        assert data["forbidden_ids"] == [str(other_experiment.id)]

        test_db.expire_all()
        with without_soft_delete_filter():
            still_present = (
                test_db.query(Experiment).filter(Experiment.id == other_experiment.id).first()
            )
        assert still_present is not None
        assert still_present.deleted_at is None

    def test_bulk_delete_mixed_owned_forbidden_not_found(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        db_project,
        db_user,
    ):
        """One owned, one forbidden, one not found. Each lands in its bucket."""
        owned = _create_experiment(authenticated_client, db_project.id, name="mine")

        other_experiment = Experiment(
            name="Someone else's",
            owner_user_id=db_user.id,
            visibility="shared",
            project_id=db_project.id,
            organization_id=db_project.organization_id,
        )
        test_db.add(other_experiment)
        test_db.flush()
        test_db.refresh(other_experiment)

        fake_id = str(uuid.uuid4())

        response = authenticated_client.request(
            "DELETE",
            "/experiments/bulk",
            json={
                "experiment_ids": [
                    owned["id"],
                    str(other_experiment.id),
                    fake_id,
                ]
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == [owned["id"]]
        assert data["forbidden_ids"] == [str(other_experiment.id)]
        assert data["not_found_ids"] == [fake_id]

    def test_bulk_delete_unbinds_environments(
        self,
        authenticated_client: TestClient,
        db_project,
    ):
        """Environments pointing at deleted experiments are unbound,
        matching single-delete behaviour."""
        _seed_schema(authenticated_client, db_project.id)
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="env-bound",
            visibility="shared",
        )
        committed = authenticated_client.post(
            _versions_url(exp["id"]),
            json={"values": {"temperature": 0.9}},
        )
        assert committed.status_code == status.HTTP_201_CREATED
        version = committed.json()["version"]

        bind = authenticated_client.put(
            _environment_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": version},
        )
        assert bind.status_code == status.HTTP_200_OK

        response = authenticated_client.request(
            "DELETE",
            "/experiments/bulk",
            json={"experiment_ids": [exp["id"]]},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["deleted_ids"] == [exp["id"]]

        envs = authenticated_client.get(_environments_url(db_project.id))
        pointer = envs.json()["environments"].get("default")
        assert pointer is None

    def test_bulk_delete_empty_list(
        self,
        authenticated_client: TestClient,
        db_project,
    ):
        response = authenticated_client.request(
            "DELETE",
            "/experiments/bulk",
            json={"experiment_ids": []},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_ids"] == []
        assert data["not_found_ids"] == []
        assert data["forbidden_ids"] == []

    def test_bulk_delete_unauthenticated(self, client: TestClient):
        response = client.request(
            "DELETE",
            "/experiments/bulk",
            json={"experiment_ids": [str(uuid.uuid4())]},
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
