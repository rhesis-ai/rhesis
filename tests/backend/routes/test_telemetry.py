"""
Tests for telemetry router in rhesis.backend.app.routers.telemetry

This module tests the OpenTelemetry trace ingestion endpoints including:
- Trace batch ingestion
- Authentication and validation
- Error handling
- Project access control
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from tests.backend.routes.fixtures.data_factories import TraceDataFactory


@pytest.mark.integration
class TestTraceIngestion:
    """Test trace ingestion functionality"""

    def test_ingest_single_span_success(self, authenticated_client: TestClient, db_project):
        """Test ingesting a single span successfully"""
        span_data = TraceDataFactory.minimal_data(project_id=str(db_project.id))

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"
        assert data["span_count"] == 1
        assert data["trace_id"] == span_data["trace_id"]

    def test_ingest_multiple_spans_success(self, authenticated_client: TestClient, db_project):
        """Test ingesting multiple spans in one batch"""
        spans_data = TraceDataFactory.batch_data(
            count=3, same_trace=True, project_id=str(db_project.id)
        )

        trace_batch = {"spans": spans_data}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"
        assert data["span_count"] == 3
        # All spans should have the same trace_id
        assert data["trace_id"] == spans_data[0]["trace_id"]

    def test_ingest_span_with_events(self, authenticated_client: TestClient, db_project):
        """Test ingesting span with events (prompts, completions)"""
        span_data = TraceDataFactory.sample_data(with_events=True, project_id=str(db_project.id))

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"
        assert len(span_data["events"]) == 2  # prompt and completion

    def test_ingest_span_with_error_status(self, authenticated_client: TestClient, db_project):
        """Test ingesting span with error status"""
        span_data = TraceDataFactory.sample_data(with_error=True, project_id=str(db_project.id))

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"
        assert span_data["status_code"] == "ERROR"

    def test_ingest_nested_spans(self, authenticated_client: TestClient, db_project):
        """Test ingesting parent and child spans"""
        project_id = str(db_project.id)
        parent_span = TraceDataFactory.sample_data(with_parent=False, project_id=project_id)
        child_span = TraceDataFactory.sample_data(with_parent=True, project_id=project_id)

        # Make child belong to parent's trace
        child_span["trace_id"] = parent_span["trace_id"]
        child_span["parent_span_id"] = parent_span["span_id"]
        child_span["project_id"] = parent_span["project_id"]

        trace_batch = {"spans": [parent_span, child_span]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"
        assert data["span_count"] == 2


@pytest.mark.integration
class TestTraceValidation:
    """Test trace validation and error handling"""

    def test_ingest_empty_batch(self, authenticated_client: TestClient):
        """Test ingesting empty batch fails validation"""
        trace_batch = {"spans": []}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_ingest_invalid_trace_id(self, authenticated_client: TestClient, db_project):
        """Test ingesting span with invalid trace_id format"""
        span_data = TraceDataFactory.minimal_data(project_id=str(db_project.id))
        span_data["trace_id"] = "invalid"  # Too short

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_ingest_invalid_span_id(self, authenticated_client: TestClient, db_project):
        """Test ingesting span with invalid span_id format"""
        span_data = TraceDataFactory.minimal_data(project_id=str(db_project.id))
        span_data["span_id"] = "short"  # Too short

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_ingest_invalid_timestamps(self, authenticated_client: TestClient, db_project):
        """Test ingesting span with end_time before start_time"""
        span_data = TraceDataFactory.minimal_data(project_id=str(db_project.id))
        # Swap start and end times
        span_data["start_time"], span_data["end_time"] = (
            span_data["end_time"],
            span_data["start_time"],
        )

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_ingest_missing_required_fields(self, authenticated_client: TestClient, db_project):
        """Test ingesting span with missing required fields"""
        span_data = TraceDataFactory.minimal_data(project_id=str(db_project.id))
        del span_data["trace_id"]  # Remove required field

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_ingest_batch_size_limit(self, authenticated_client: TestClient, db_project):
        """Test ingesting batch exceeding size limit"""
        # Generate more than 1000 spans (the limit)
        spans_data = TraceDataFactory.batch_data(
            count=1001, same_trace=False, project_id=str(db_project.id)
        )

        trace_batch = {"spans": spans_data}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.integration
class TestTraceAuthentication:
    """Test authentication and authorization for trace ingestion"""

    def test_ingest_without_authentication(self, client: TestClient):
        """Test ingesting trace without authentication fails"""
        span_data = TraceDataFactory.minimal_data()
        trace_batch = {"spans": [span_data]}

        response = client.post("/telemetry/traces", json=trace_batch)

        # Should fail authentication
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_ingest_with_valid_authentication(self, authenticated_client: TestClient, db_project):
        """Test ingesting trace with valid authentication succeeds"""
        span_data = TraceDataFactory.minimal_data(project_id=str(db_project.id))
        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.integration
class TestTraceEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_ingest_span_with_large_attributes(self, authenticated_client: TestClient, db_project):
        """Test ingesting span with large attribute payload"""
        span_data = TraceDataFactory.edge_case_data("large_attributes")
        span_data["project_id"] = str(db_project.id)

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"

    def test_ingest_minimal_span(self, authenticated_client: TestClient, db_project):
        """Test ingesting span with only required fields"""
        span_data = TraceDataFactory.edge_case_data("minimal")
        span_data["project_id"] = str(db_project.id)

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"

    def test_ingest_span_with_unicode_content(self, authenticated_client: TestClient, db_project):
        """Test ingesting span with unicode characters"""
        span_data = TraceDataFactory.sample_data(project_id=str(db_project.id))
        span_data["attributes"]["user_input"] = "Hello 世界 🌍"

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"

    def test_ingest_span_with_empty_attributes(self, authenticated_client: TestClient, db_project):
        """Test ingesting span with empty attributes"""
        span_data = TraceDataFactory.minimal_data(project_id=str(db_project.id))
        span_data["attributes"] = {}

        trace_batch = {"spans": [span_data]}

        response = authenticated_client.post("/telemetry/traces", json=trace_batch)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"

    def test_ingest_different_environments(self, authenticated_client: TestClient, db_project):
        """Test ingesting spans from different environments"""
        for environment in ["development", "staging", "production"]:
            span_data = TraceDataFactory.minimal_data(project_id=str(db_project.id))
            span_data["environment"] = environment

            trace_batch = {"spans": [span_data]}

            response = authenticated_client.post("/telemetry/traces", json=trace_batch)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "received"


@pytest.mark.unit
class TestTraceDataFactory:
    """Test the TraceDataFactory itself"""

    def test_minimal_data_has_required_fields(self):
        """Test minimal_data generates all required fields"""
        data = TraceDataFactory.minimal_data()

        required_fields = [
            "trace_id",
            "span_id",
            "project_id",
            "environment",
            "span_name",
            "span_kind",
            "start_time",
            "end_time",
            "status_code",
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_sample_data_has_attributes(self):
        """Test sample_data includes attributes"""
        data = TraceDataFactory.sample_data()

        assert "attributes" in data
        assert len(data["attributes"]) > 0
        assert "ai.operation.type" in data["attributes"]

    def test_batch_data_same_trace(self):
        """Test batch_data with same_trace=True"""
        spans = TraceDataFactory.batch_data(count=5, same_trace=True)

        assert len(spans) == 5
        # All spans should have the same trace_id
        trace_ids = {span["trace_id"] for span in spans}
        assert len(trace_ids) == 1

    def test_batch_data_different_traces(self):
        """Test batch_data with same_trace=False"""
        spans = TraceDataFactory.batch_data(count=5, same_trace=False)

        assert len(spans) == 5
        # All spans should have different trace_ids
        trace_ids = {span["trace_id"] for span in spans}
        assert len(trace_ids) == 5

    def test_trace_id_format(self):
        """Test trace_id is 32-character hex string"""
        data = TraceDataFactory.minimal_data()

        assert len(data["trace_id"]) == 32
        assert all(c in "0123456789abcdef" for c in data["trace_id"])

    def test_span_id_format(self):
        """Test span_id is 16-character hex string"""
        data = TraceDataFactory.minimal_data()

        assert len(data["span_id"]) == 16
        assert all(c in "0123456789abcdef" for c in data["span_id"])
