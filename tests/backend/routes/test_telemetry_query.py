"""
Tests for telemetry query endpoints in rhesis.backend.app.routers.telemetry

This module tests the telemetry query endpoints including:
- GET /telemetry/traces - List traces with filtering and pagination
- GET /telemetry/traces/{trace_id} - Get detailed trace information
- GET /telemetry/metrics - Get aggregated metrics
- Authentication and validation
- Error handling and edge cases
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from tests.backend.routes.fixtures.data_factories import TraceDataFactory


@pytest.mark.integration
class TestTraceListEndpoint:
    """Test GET /telemetry/traces endpoint with filtering and pagination"""

    def test_list_traces_basic(self, authenticated_client: TestClient, db_project):
        """Test basic trace listing without filters"""
        # First, create some test traces by ingesting them
        spans_data = TraceDataFactory.batch_data(
            count=3, same_trace=False, project_id=str(db_project.id)
        )

        for span_data in spans_data:
            trace_batch = {"spans": [span_data]}
            response = authenticated_client.post("/telemetry/traces", json=trace_batch)
            assert response.status_code == status.HTTP_200_OK

        # Now query the traces
        response = authenticated_client.get(f"/telemetry/traces?project_id={db_project.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "traces" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert data["limit"] == 100  # Default limit
        assert data["offset"] == 0  # Default offset
        assert len(data["traces"]) >= 3  # At least our test traces

    def test_list_traces_with_pagination(self, authenticated_client: TestClient, db_project):
        """Test trace listing with pagination parameters"""
        # Create test traces
        spans_data = TraceDataFactory.batch_data(
            count=5, same_trace=False, project_id=str(db_project.id)
        )

        for span_data in spans_data:
            trace_batch = {"spans": [span_data]}
            authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Test pagination
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&limit=2&offset=1"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["limit"] == 2
        assert data["offset"] == 1
        assert len(data["traces"]) <= 2

    def test_list_traces_filter_by_environment(self, authenticated_client: TestClient, db_project):
        """Test filtering traces by environment"""
        # Create traces with different environments
        dev_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        dev_span["environment"] = "development"

        prod_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        prod_span["environment"] = "production"

        # Ingest both traces
        for span_data in [dev_span, prod_span]:
            trace_batch = {"spans": [span_data]}
            authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Filter by development environment
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&environment=development"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned traces should be from development environment
        for trace in data["traces"]:
            assert trace["environment"] == "development"

    def test_list_traces_filter_by_span_name(self, authenticated_client: TestClient, db_project):
        """Test filtering traces by span name"""
        # Create traces with different span names
        llm_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        llm_span["span_name"] = "ai.llm.invoke"

        tool_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        tool_span["span_name"] = "ai.tool.invoke"

        # Ingest both traces
        for span_data in [llm_span, tool_span]:
            trace_batch = {"spans": [span_data]}
            authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Filter by LLM spans
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&span_name=ai.llm.invoke"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned traces should have LLM operation
        for trace in data["traces"]:
            assert trace["root_operation"] == "ai.llm.invoke"

    def test_list_traces_filter_by_status_code(self, authenticated_client: TestClient, db_project):
        """Test filtering traces by status code"""
        # Create traces with different status codes
        ok_span = TraceDataFactory.sample_data(project_id=str(db_project.id), with_error=False)
        error_span = TraceDataFactory.sample_data(project_id=str(db_project.id), with_error=True)

        # Ingest both traces
        for span_data in [ok_span, error_span]:
            trace_batch = {"spans": [span_data]}
            authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Filter by error status
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&status_code=ERROR"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned traces should have error status
        for trace in data["traces"]:
            assert trace["status_code"] == "ERROR"
            assert trace["has_errors"] is True

    def test_list_traces_filter_by_time_range(self, authenticated_client: TestClient, db_project):
        """Test filtering traces by time range"""
        # Create a trace with specific timestamp
        now = datetime.now(timezone.utc)
        past_time = now - timedelta(hours=2)
        future_time = now + timedelta(hours=1)

        span_data = TraceDataFactory.sample_data(project_id=str(db_project.id))
        span_data["start_time"] = now.isoformat()

        # Ingest the trace
        trace_batch = {"spans": [span_data]}
        authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Filter by time range that includes our trace
        # Use URL encoding for the datetime strings
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}"
            f"&start_time_after={past_time.strftime('%Y-%m-%dT%H:%M:%S')}"
            f"&start_time_before={future_time.strftime('%Y-%m-%dT%H:%M:%S')}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["traces"]) >= 1

        # Filter by time range that excludes our trace
        very_past_time = now - timedelta(days=1)
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}"
            f"&start_time_after={very_past_time.strftime('%Y-%m-%dT%H:%M:%S')}"
            f"&start_time_before={past_time.strftime('%Y-%m-%dT%H:%M:%S')}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should have fewer traces (or none) in this old time range
        assert data["total"] >= 0

    def test_list_traces_pagination_limits(self, authenticated_client: TestClient, db_project):
        """Test pagination limits and validation"""
        # Test maximum limit
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&limit=1001"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test minimum limit
        response = authenticated_client.get(f"/telemetry/traces?project_id={db_project.id}&limit=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test negative offset
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&offset=-1"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_traces_pagination_total_with_filters(
        self, authenticated_client: TestClient, db_project
    ):
        """
        Test that pagination total count respects filters.

        This test verifies the fix for the issue where count_traces was missing
        environment, span_name, and status_code filters, causing incorrect total
        counts when those filters were applied.
        """
        # Create traces with different characteristics
        # 3 development + 3 production traces
        for i in range(3):
            dev_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
            dev_span["environment"] = "development"
            dev_span["span_name"] = "ai.llm.invoke"
            dev_span["status_code"] = "OK"

            prod_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
            prod_span["environment"] = "production"
            prod_span["span_name"] = "ai.tool.invoke"
            prod_span["status_code"] = "ERROR"

            for span_data in [dev_span, prod_span]:
                trace_batch = {"spans": [span_data]}
                authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Test 1: Filter by environment only
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&environment=development&limit=2"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Total should only count development traces (3)
        dev_count = data["total"]
        assert dev_count >= 3
        # Should only get development traces in results
        for trace in data["traces"]:
            assert trace["environment"] == "development"

        # Test 2: Filter by span_name only
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&span_name=ai.llm.invoke&limit=2"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Total should only count LLM invocations (3)
        llm_count = data["total"]
        assert llm_count >= 3
        for trace in data["traces"]:
            assert trace["root_operation"] == "ai.llm.invoke"

        # Test 3: Filter by status_code only
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&status_code=ERROR&limit=2"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Total should only count error traces (3)
        error_count = data["total"]
        assert error_count >= 3
        for trace in data["traces"]:
            assert trace["status_code"] == "ERROR"

        # Test 4: Combine multiple filters
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}"
            f"&environment=production&span_name=ai.tool.invoke&status_code=ERROR&limit=2"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Total should only count production tool invocations with errors (3)
        combined_count = data["total"]
        assert combined_count >= 3
        for trace in data["traces"]:
            assert trace["environment"] == "production"
            assert trace["root_operation"] == "ai.tool.invoke"
            assert trace["status_code"] == "ERROR"

        # Verify counts are different (filters are working)
        # Without filters, total would be 6+
        # With filters, we should see exactly 3 each
        assert combined_count < dev_count + error_count

    def test_list_traces_response_structure(self, authenticated_client: TestClient, db_project):
        """Test that trace list response has correct structure"""
        # Create a trace with enriched data
        span_data = TraceDataFactory.sample_data(project_id=str(db_project.id))
        trace_batch = {"spans": [span_data]}
        authenticated_client.post("/telemetry/traces", json=trace_batch)

        response = authenticated_client.get(f"/telemetry/traces?project_id={db_project.id}&limit=1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check response structure
        assert "traces" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

        if data["traces"]:
            trace = data["traces"][0]
            # Check trace summary structure
            required_fields = [
                "trace_id",
                "project_id",
                "environment",
                "start_time",
                "duration_ms",
                "span_count",
                "root_operation",
                "status_code",
                "has_errors",
            ]
            for field in required_fields:
                assert field in trace

            # Optional fields should be present but may be null
            optional_fields = ["total_tokens", "total_cost_usd"]
            for field in optional_fields:
                assert field in trace


@pytest.mark.integration
class TestTraceDetailEndpoint:
    """Test GET /telemetry/traces/{trace_id} endpoint"""

    def test_get_trace_detail_success(self, authenticated_client: TestClient, db_project):
        """Test getting detailed trace information"""
        # Create a trace with multiple spans
        spans_data = TraceDataFactory.batch_data(
            count=3, same_trace=True, project_id=str(db_project.id)
        )
        trace_id = spans_data[0]["trace_id"]

        # Ingest the trace
        trace_batch = {"spans": spans_data}
        response = authenticated_client.post("/telemetry/traces", json=trace_batch)
        assert response.status_code == status.HTTP_200_OK

        # Get trace details
        response = authenticated_client.get(
            f"/telemetry/traces/{trace_id}?project_id={db_project.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check response structure
        required_fields = [
            "trace_id",
            "project_id",
            "environment",
            "start_time",
            "end_time",
            "duration_ms",
            "span_count",
            "error_count",
            "total_tokens",
            "total_cost_usd",
            "root_spans",
        ]
        for field in required_fields:
            assert field in data

        assert data["trace_id"] == trace_id
        assert data["project_id"] == str(db_project.id)
        assert data["span_count"] == 3
        assert len(data["root_spans"]) >= 1

    def test_get_trace_detail_not_found(self, authenticated_client: TestClient, db_project):
        """Test getting non-existent trace returns 404"""
        fake_trace_id = "nonexistent" + "0" * 24  # 32-char hex string

        response = authenticated_client.get(
            f"/telemetry/traces/{fake_trace_id}?project_id={db_project.id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_trace_detail_span_structure(self, authenticated_client: TestClient, db_project):
        """Test that span nodes have correct structure"""
        # Create a trace with events
        span_data = TraceDataFactory.sample_data(project_id=str(db_project.id), with_events=True)
        trace_id = span_data["trace_id"]

        # Ingest the trace
        trace_batch = {"spans": [span_data]}
        authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Get trace details
        response = authenticated_client.get(
            f"/telemetry/traces/{trace_id}?project_id={db_project.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check span node structure
        if data["root_spans"]:
            span_node = data["root_spans"][0]
            required_span_fields = [
                "span_id",
                "span_name",
                "span_kind",
                "start_time",
                "end_time",
                "duration_ms",
                "status_code",
                "attributes",
                "events",
                "children",
            ]
            for field in required_span_fields:
                assert field in span_node

            # Check that events are included
            assert isinstance(span_node["events"], list)
            assert isinstance(span_node["attributes"], dict)
            assert isinstance(span_node["children"], list)

    def test_get_trace_detail_missing_project_id(self, authenticated_client: TestClient):
        """Test that project_id query parameter is required"""
        fake_trace_id = "test" + "0" * 28

        response = authenticated_client.get(f"/telemetry/traces/{fake_trace_id}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.integration
class TestMetricsEndpoint:
    """Test GET /telemetry/metrics endpoint"""

    def test_get_metrics_basic(self, authenticated_client: TestClient, db_project):
        """Test basic metrics aggregation"""
        # Create traces with different characteristics
        spans_data = []

        # LLM span with tokens
        llm_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        llm_span["span_name"] = "ai.llm.invoke"
        llm_span["attributes"]["ai.llm.tokens.total"] = 100
        spans_data.append(llm_span)

        # Tool span
        tool_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        tool_span["span_name"] = "ai.tool.invoke"
        spans_data.append(tool_span)

        # Error span
        error_span = TraceDataFactory.sample_data(project_id=str(db_project.id), with_error=True)
        spans_data.append(error_span)

        # Ingest all spans
        for span_data in spans_data:
            trace_batch = {"spans": [span_data]}
            authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Get metrics
        response = authenticated_client.get(f"/telemetry/metrics?project_id={db_project.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check response structure
        required_fields = [
            "total_traces",
            "total_spans",
            "total_tokens",
            "total_cost_usd",
            "error_rate",
            "avg_duration_ms",
            "p50_duration_ms",
            "p95_duration_ms",
            "p99_duration_ms",
            "operation_breakdown",
        ]
        for field in required_fields:
            assert field in data

        # Check that we have data
        assert data["total_traces"] >= 3
        assert data["total_spans"] >= 3
        assert data["error_rate"] >= 0.0
        assert isinstance(data["operation_breakdown"], dict)

    def test_get_metrics_with_time_filter(self, authenticated_client: TestClient, db_project):
        """Test metrics with time range filtering"""
        # Create a trace
        span_data = TraceDataFactory.sample_data(project_id=str(db_project.id))
        trace_batch = {"spans": [span_data]}
        authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Get metrics for a specific time range
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=1)
        end_time = now + timedelta(hours=1)

        response = authenticated_client.get(
            f"/telemetry/metrics?project_id={db_project.id}"
            f"&start_time_after={start_time.strftime('%Y-%m-%dT%H:%M:%S')}"
            f"&start_time_before={end_time.strftime('%Y-%m-%dT%H:%M:%S')}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_traces"] >= 1

    def test_get_metrics_with_environment_filter(
        self, authenticated_client: TestClient, db_project
    ):
        """Test metrics with environment filtering"""
        # Create traces in different environments
        dev_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        dev_span["environment"] = "development"

        prod_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        prod_span["environment"] = "production"

        # Ingest both
        for span_data in [dev_span, prod_span]:
            trace_batch = {"spans": [span_data]}
            authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Get metrics for development only
        response = authenticated_client.get(
            f"/telemetry/metrics?project_id={db_project.id}&environment=development"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should have at least our development trace
        assert data["total_traces"] >= 1

    def test_get_metrics_empty_dataset(self, authenticated_client: TestClient, db_project):
        """Test metrics when no traces exist"""
        # Query metrics for a time range with no data
        past_time = datetime.now(timezone.utc) - timedelta(days=30)
        very_past_time = past_time - timedelta(days=1)

        response = authenticated_client.get(
            f"/telemetry/metrics?project_id={db_project.id}"
            f"&start_time_after={very_past_time.strftime('%Y-%m-%dT%H:%M:%S')}"
            f"&start_time_before={past_time.strftime('%Y-%m-%dT%H:%M:%S')}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return zero metrics
        assert data["total_traces"] == 0
        assert data["total_spans"] == 0
        assert data["total_tokens"] == 0
        assert data["total_cost_usd"] == 0
        assert data["error_rate"] == 0
        assert data["operation_breakdown"] == {}

    def test_get_metrics_operation_breakdown(self, authenticated_client: TestClient, db_project):
        """Test that operation breakdown is calculated correctly"""
        # Create spans with different operation types
        operations = ["ai.llm.invoke", "ai.tool.invoke", "ai.retrieval", "ai.embedding.generate"]

        for operation in operations:
            span_data = TraceDataFactory.sample_data(project_id=str(db_project.id))
            span_data["span_name"] = operation
            span_data["attributes"]["ai.operation.type"] = operation.replace("ai.", "")

            trace_batch = {"spans": [span_data]}
            authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Get metrics
        response = authenticated_client.get(f"/telemetry/metrics?project_id={db_project.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check operation breakdown
        breakdown = data["operation_breakdown"]
        assert isinstance(breakdown, dict)
        assert len(breakdown) >= 1  # Should have at least some operations


@pytest.mark.integration
class TestQueryAuthentication:
    """Test authentication and authorization for query endpoints"""

    def test_list_traces_without_auth(self, client: TestClient, db_project):
        """Test that listing traces requires authentication"""
        response = client.get(f"/telemetry/traces?project_id={db_project.id}")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_get_trace_detail_without_auth(self, client: TestClient, db_project):
        """Test that getting trace details requires authentication"""
        fake_trace_id = "test" + "0" * 28
        response = client.get(f"/telemetry/traces/{fake_trace_id}?project_id={db_project.id}")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_get_metrics_without_auth(self, client: TestClient, db_project):
        """Test that getting metrics requires authentication"""
        response = client.get(f"/telemetry/metrics?project_id={db_project.id}")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_query_endpoints_with_valid_auth(self, authenticated_client: TestClient, db_project):
        """Test that all query endpoints work with valid authentication"""
        # List traces
        response = authenticated_client.get(f"/telemetry/traces?project_id={db_project.id}")
        assert response.status_code == status.HTTP_200_OK

        # Get metrics
        response = authenticated_client.get(f"/telemetry/metrics?project_id={db_project.id}")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.integration
class TestQueryValidation:
    """Test input validation for query endpoints"""

    def test_list_traces_missing_project_id(self, authenticated_client: TestClient):
        """Test that project_id is required for listing traces"""
        response = authenticated_client.get("/telemetry/traces")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_metrics_missing_project_id(self, authenticated_client: TestClient):
        """Test that project_id is required for metrics"""
        response = authenticated_client.get("/telemetry/metrics")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_traces_invalid_datetime(self, authenticated_client: TestClient, db_project):
        """Test that invalid datetime formats are rejected"""
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&start_time_after=invalid-date"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Note: UUID validation happens at database level, which is appropriate
    # Invalid UUIDs will result in database errors, which is the expected behavior


@pytest.mark.integration
class TestQueryEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_list_traces_very_large_offset(self, authenticated_client: TestClient, db_project):
        """Test listing traces with very large offset"""
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&offset=999999"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["traces"] == []  # Should return empty list
        assert data["offset"] == 999999

    def test_get_trace_detail_malformed_trace_id(
        self, authenticated_client: TestClient, db_project
    ):
        """Test getting trace with malformed trace ID"""
        malformed_id = "short"  # Too short for a trace ID

        response = authenticated_client.get(
            f"/telemetry/traces/{malformed_id}?project_id={db_project.id}"
        )

        # Should return 404 (not found) rather than validation error
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_metrics_with_future_time_range(self, authenticated_client: TestClient, db_project):
        """Test metrics with future time range (should return empty results)"""
        future_start = datetime.now(timezone.utc) + timedelta(days=1)
        future_end = future_start + timedelta(days=1)

        response = authenticated_client.get(
            f"/telemetry/metrics?project_id={db_project.id}"
            f"&start_time_after={future_start.strftime('%Y-%m-%dT%H:%M:%S')}"
            f"&start_time_before={future_end.strftime('%Y-%m-%dT%H:%M:%S')}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_traces"] == 0

    def test_list_traces_with_enriched_data(self, authenticated_client: TestClient, db_project):
        """Test that traces with enriched data show cost information"""
        # Create a trace
        span_data = TraceDataFactory.sample_data(project_id=str(db_project.id))
        trace_batch = {"spans": [span_data]}
        authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Mock enrichment to add cost data
        with patch(
            "rhesis.backend.app.services.telemetry.enrichment_service.EnrichmentService._check_workers_available",
            return_value=False,
        ):
            # This will trigger sync enrichment
            response = authenticated_client.get(
                f"/telemetry/traces?project_id={db_project.id}&limit=1"
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            if data["traces"]:
                trace = data["traces"][0]
                # Cost fields should be present (may be null if no enrichment occurred)
                assert "total_cost_usd" in trace
                assert "total_tokens" in trace


@pytest.mark.unit
class TestQueryDataFactories:
    """Test that our data factories work correctly for query tests"""

    def test_trace_data_factory_batch_same_trace(self):
        """Test that batch_data with same_trace=True creates related spans"""
        spans = TraceDataFactory.batch_data(count=3, same_trace=True)

        assert len(spans) == 3
        # All spans should have the same trace_id
        trace_ids = {span["trace_id"] for span in spans}
        assert len(trace_ids) == 1

        # First span should be root, others should have parent
        assert "parent_span_id" not in spans[0] or spans[0]["parent_span_id"] is None
        for span in spans[1:]:
            assert span["parent_span_id"] == spans[0]["span_id"]

    def test_trace_data_factory_different_traces(self):
        """Test that batch_data with same_trace=False creates separate traces"""
        spans = TraceDataFactory.batch_data(count=3, same_trace=False)

        assert len(spans) == 3
        # All spans should have different trace_ids
        trace_ids = {span["trace_id"] for span in spans}
        assert len(trace_ids) == 3

    def test_trace_data_factory_with_events(self):
        """Test that sample_data with events creates proper event structure"""
        span = TraceDataFactory.sample_data(with_events=True)

        assert "events" in span
        assert isinstance(span["events"], list)
        assert len(span["events"]) >= 1

        # Check event structure
        for event in span["events"]:
            assert "name" in event
            assert "timestamp" in event
            assert "attributes" in event

    def test_trace_data_factory_with_error(self):
        """Test that sample_data with error creates error span"""
        span = TraceDataFactory.sample_data(with_error=True)

        assert span["status_code"] == "ERROR"
        assert span["status_message"] is not None
