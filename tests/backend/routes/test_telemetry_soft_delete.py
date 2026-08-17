"""
Regression coverage for the trace soft-delete contract.

get_trace_by_db_id must raise ItemDeletedException for a soft-deleted trace, like
every other entity's single-item fetch, instead of silently returning None -- and
routes built on it (e.g. add_trace_review) must surface that as 410 GONE, not a
bare 404.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app import models
from rhesis.backend.app.crud.telemetry import get_trace_by_db_id
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from tests.backend.routes.fixtures.data_factories import TraceDataFactory


def _ingest_trace(client: TestClient, project_id: str) -> dict:
    span_data = TraceDataFactory.sample_data(project_id=project_id)
    trace_batch = {"spans": [span_data]}
    response = client.post("/telemetry/traces", json=trace_batch)
    assert response.status_code == status.HTTP_200_OK
    return {"trace_id": span_data["trace_id"], "db_id": response.json().get("trace_db_id")}


def _get_trace_db_id(client: TestClient, project_id: str, trace_id: str) -> str:
    response = client.get(f"/telemetry/traces/{trace_id}?project_id={project_id}")
    assert response.status_code == status.HTTP_200_OK
    root_spans = response.json().get("root_spans", [])
    assert root_spans
    return root_spans[0]["id"]


@pytest.mark.integration
class TestTraceSoftDeleteContract:
    def test_get_trace_by_db_id_raises_for_deleted(
        self, test_db, authenticated_client: TestClient, db_project, test_org_id: str
    ):
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        trace = test_db.query(models.Trace).filter(models.Trace.id == trace_db_id).first()
        trace.deleted_at = datetime.now(timezone.utc)
        test_db.commit()

        with pytest.raises(ItemDeletedException):
            get_trace_by_db_id(test_db, trace_db_id, test_org_id)

    def test_add_review_on_deleted_trace_returns_410(
        self, test_db, authenticated_client: TestClient, db_project
    ):
        ingested = _ingest_trace(authenticated_client, str(db_project.id))
        trace_db_id = _get_trace_db_id(
            authenticated_client, str(db_project.id), ingested["trace_id"]
        )

        trace = test_db.query(models.Trace).filter(models.Trace.id == trace_db_id).first()
        trace.deleted_at = datetime.now(timezone.utc)
        test_db.commit()

        response = authenticated_client.post(
            f"/telemetry/traces/{trace_db_id}/reviews",
            json={
                "status_id": str(uuid.uuid4()),
                "comments": "should not get here",
                "target": {"type": "trace", "reference": None},
            },
        )

        assert response.status_code == status.HTTP_410_GONE
