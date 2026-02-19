"""Tests for conversation_id support in telemetry routes.

Tests cover:
- Ingesting spans with conversation_id
- Filtering traces by conversation_id in list endpoint
- get_trace_id_for_conversation CRUD function
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from tests.backend.routes.fixtures.data_factories import TraceDataFactory


@pytest.mark.integration
class TestConversationTraceIngestion:
    """Test ingesting traces with conversation_id."""

    def test_ingest_span_with_conversation_id(self, authenticated_client: TestClient, db_project):
        """Span with conversation_id is accepted."""
        span_data = TraceDataFactory.minimal_data(project_id=str(db_project.id))
        span_data["conversation_id"] = "session-abc-123"

        response = authenticated_client.post("/telemetry/traces", json={"spans": [span_data]})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"
        assert data["span_count"] == 1

    def test_ingest_span_without_conversation_id(
        self, authenticated_client: TestClient, db_project
    ):
        """Span without conversation_id is still accepted (field is nullable)."""
        span_data = TraceDataFactory.minimal_data(project_id=str(db_project.id))
        span_data.pop("conversation_id", None)

        response = authenticated_client.post("/telemetry/traces", json={"spans": [span_data]})

        assert response.status_code == status.HTTP_200_OK

    def test_ingest_multiple_spans_same_conversation(
        self, authenticated_client: TestClient, db_project
    ):
        """Multiple spans sharing a conversation_id and trace_id are accepted."""
        project_id = str(db_project.id)
        spans = TraceDataFactory.batch_data(count=3, same_trace=True, project_id=project_id)
        for span in spans:
            span["conversation_id"] = "multi-turn-session"

        response = authenticated_client.post("/telemetry/traces", json={"spans": spans})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["span_count"] == 3


@pytest.mark.integration
class TestConversationTraceFiltering:
    """Test filtering traces by conversation_id in the list endpoint."""

    def _ingest_span(self, client, project_id, conversation_id=None, trace_id=None):
        """Helper to ingest a single span and return the span data."""
        span_data = TraceDataFactory.minimal_data(project_id=project_id)
        if conversation_id:
            span_data["conversation_id"] = conversation_id
        if trace_id:
            span_data["trace_id"] = trace_id
        resp = client.post("/telemetry/traces", json={"spans": [span_data]})
        assert resp.status_code == status.HTTP_200_OK
        return span_data

    def test_filter_by_conversation_id(self, authenticated_client: TestClient, db_project):
        """Listing traces with conversation_id filter returns only matching traces."""
        project_id = str(db_project.id)

        # Ingest spans with different conversation_ids
        self._ingest_span(authenticated_client, project_id, conversation_id="conv-filter-A")
        self._ingest_span(authenticated_client, project_id, conversation_id="conv-filter-B")
        self._ingest_span(authenticated_client, project_id, conversation_id="conv-filter-A")

        # Filter by conversation_id=conv-filter-A
        response = authenticated_client.get(
            "/telemetry/traces",
            params={
                "project_id": project_id,
                "conversation_id": "conv-filter-A",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] >= 2
        for trace_item in data["traces"]:
            assert trace_item["conversation_id"] == "conv-filter-A"

    def test_filter_nonexistent_conversation_returns_empty(
        self, authenticated_client: TestClient, db_project
    ):
        """Filtering by a non-existent conversation_id returns zero results."""
        response = authenticated_client.get(
            "/telemetry/traces",
            params={
                "project_id": str(db_project.id),
                "conversation_id": "does-not-exist-xyz",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 0
        assert data["traces"] == []

    def test_conversation_id_in_trace_detail(self, authenticated_client: TestClient, db_project):
        """Trace detail response includes conversation_id."""
        project_id = str(db_project.id)
        span_data = self._ingest_span(
            authenticated_client,
            project_id,
            conversation_id="conv-detail-test",
        )

        # Get the trace detail
        response = authenticated_client.get(
            f"/telemetry/traces/{span_data['trace_id']}",
            params={"project_id": project_id},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["conversation_id"] == "conv-detail-test"


@pytest.mark.integration
class TestGetTraceIdForConversation:
    """Test the CRUD function get_trace_id_for_conversation."""

    def _ingest_and_get_db(self, client, project_id, conversation_id, trace_id=None):
        """Ingest a span and return its trace_id."""
        span_data = TraceDataFactory.minimal_data(project_id=project_id)
        span_data["conversation_id"] = conversation_id
        if trace_id:
            span_data["trace_id"] = trace_id
        resp = client.post("/telemetry/traces", json={"spans": [span_data]})
        assert resp.status_code == status.HTTP_200_OK
        return span_data["trace_id"]

    def test_returns_trace_id_for_existing_conversation(
        self, authenticated_client: TestClient, db_project, test_db
    ):
        """Returns the trace_id for an existing conversation."""
        from rhesis.backend.app import crud

        project_id = str(db_project.id)
        conversation_id = "crud-test-conv-1"

        ingested_trace_id = self._ingest_and_get_db(
            authenticated_client, project_id, conversation_id
        )

        org_id = str(db_project.organization_id)
        result = crud.get_trace_id_for_conversation(
            db=test_db,
            conversation_id=conversation_id,
            project_id=project_id,
            organization_id=org_id,
        )

        assert result == ingested_trace_id

    def test_returns_none_for_unknown_conversation(self, db_project, test_db):
        """Returns None when no trace exists for the conversation."""
        from rhesis.backend.app import crud

        result = crud.get_trace_id_for_conversation(
            db=test_db,
            conversation_id="nonexistent-conv",
            project_id=str(db_project.id),
            organization_id=str(db_project.organization_id),
        )

        assert result is None

    def test_returns_earliest_trace_id(self, authenticated_client: TestClient, db_project, test_db):
        """When multiple traces exist for a conversation, returns the earliest."""
        from rhesis.backend.app import crud

        project_id = str(db_project.id)
        conversation_id = "crud-test-earliest"

        # Ingest two spans with same conversation but different trace_ids
        first_trace_id = self._ingest_and_get_db(authenticated_client, project_id, conversation_id)
        self._ingest_and_get_db(authenticated_client, project_id, conversation_id)

        org_id = str(db_project.organization_id)
        result = crud.get_trace_id_for_conversation(
            db=test_db,
            conversation_id=conversation_id,
            project_id=project_id,
            organization_id=org_id,
        )

        # Should be the first one ingested (earliest created_at)
        assert result == first_trace_id
