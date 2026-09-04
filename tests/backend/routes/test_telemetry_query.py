"""
Tests for telemetry query endpoints in rhesis.backend.app.routers.telemetry

This module tests the telemetry query endpoints including:
- GET /telemetry/traces - List traces with filtering and pagination
- GET /telemetry/traces/{trace_id} - Get detailed trace information
- GET /telemetry/metrics - Get aggregated metrics
- Authentication and validation
- Error handling and edge cases
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.crud.project import create_project
from rhesis.backend.app.crud.telemetry import (
    create_trace_spans,
    get_trace_by_id,
    query_traces,
)
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

    def test_list_traces_search_partial_span_name(
        self, authenticated_client: TestClient, db_project
    ):
        """Search uses case-insensitive substring match on span names (any span in trace)."""
        root_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        root_span["span_name"] = "function.endpoint_rest_invoke"
        root_span["parent_span_id"] = None

        child_span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        child_span["trace_id"] = root_span["trace_id"]
        child_span["span_name"] = "ai.llm.invoke"
        child_span["parent_span_id"] = root_span["span_id"]

        for span_data in [root_span, child_span]:
            authenticated_client.post("/telemetry/traces", json={"spans": [span_data]})

        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&search=llm"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] >= 1
        assert any(t["trace_id"] == root_span["trace_id"] for t in data["traces"])

        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&search=rest"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] >= 1
        assert any(t["root_operation"] == "function.endpoint_rest_invoke" for t in data["traces"])

    def test_list_traces_search_endpoint_name_in_attributes(
        self, authenticated_client: TestClient, db_project
    ):
        """Search matches endpoint metadata stored on span attributes."""
        span = TraceDataFactory.sample_data(project_id=str(db_project.id))
        span["span_name"] = "function.endpoint_rest_invoke"
        span["attributes"]["endpoint.name"] = "Insurance Chatbot Unique"

        authenticated_client.post("/telemetry/traces", json={"spans": [span]})

        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&search=insurance%20chatbot"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] >= 1
        assert any(t["trace_id"] == span["trace_id"] for t in data["traces"])

    def test_list_traces_filter_by_span_name(self, authenticated_client: TestClient, db_project):
        """Test filtering traces by exact span name (legacy param)"""
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

        This test verifies that the pagination total (computed via window
        function in query_traces) correctly respects filters like
        environment, span_name, and status_code.
        """
        # Create traces with different characteristics
        # 3 development + 3 production traces
        for _i in range(3):
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
            optional_fields = [
                "total_tokens",
                "total_cost_usd",
                "has_reviews",
                "last_review",
                "matches_review",
            ]
            for field in optional_fields:
                assert field in trace

    def test_list_traces_root_spans_only_parameter(
        self, authenticated_client: TestClient, db_project
    ):
        """Test that root_spans_only parameter controls span filtering"""
        # Create trace data with parent-child spans
        spans_data = TraceDataFactory.batch_data(
            count=3, same_trace=True, project_id=str(db_project.id)
        )
        trace_id = spans_data[0]["trace_id"]

        # Ingest all spans
        for span_data in spans_data:
            trace_batch = {"spans": [span_data]}
            authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Default behavior (root_spans_only=true) - should return only 1 trace
        response = authenticated_client.get(f"/telemetry/traces?project_id={db_project.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Count how many traces have this trace_id
        matching_traces = [t for t in data["traces"] if t["trace_id"] == trace_id]
        assert len(matching_traces) == 1, "Default should return only root span"

        # Request all spans (root_spans_only=false)
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&root_spans_only=false"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return all 3 spans
        matching_spans = [t for t in data["traces"] if t["trace_id"] == trace_id]
        assert len(matching_spans) == 3, "root_spans_only=false should return all spans"

    def test_list_traces_trace_source_filter(self, authenticated_client: TestClient, db_project):
        """Test that trace_source parameter filters test vs operation traces"""
        # Create normal operation traces (without test_run_id)
        op_span1 = TraceDataFactory.sample_data(project_id=str(db_project.id))
        op_span1["environment"] = "production"
        trace_batch = {"spans": [op_span1]}
        authenticated_client.post("/telemetry/traces", json=trace_batch)

        op_span2 = TraceDataFactory.sample_data(project_id=str(db_project.id))
        op_span2["environment"] = "staging"
        trace_batch = {"spans": [op_span2]}
        authenticated_client.post("/telemetry/traces", json=trace_batch)

        # Test 'all' filter (default) - should include both operation traces
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&trace_source=all"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        all_trace_ids = {t["trace_id"] for t in data["traces"]}
        assert op_span1["trace_id"] in all_trace_ids
        assert op_span2["trace_id"] in all_trace_ids

        # Test 'operation' filter - should only include operation traces
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&trace_source=operation"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        op_trace_ids = {t["trace_id"] for t in data["traces"]}
        assert op_span1["trace_id"] in op_trace_ids
        assert op_span2["trace_id"] in op_trace_ids

        # Test 'test' filter - should not include any operation traces
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&trace_source=test"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        test_trace_ids = {t["trace_id"] for t in data["traces"]}
        # Should not include operation traces
        assert op_span1["trace_id"] not in test_trace_ids
        assert op_span2["trace_id"] not in test_trace_ids

    def test_list_traces_filter_by_endpoint(
        self,
        authenticated_client: TestClient,
        test_db,
        db_project,
        authenticated_user_id,
        test_organization,
    ):
        """Test filtering traces by endpoint_id"""
        from datetime import timezone
        from uuid import uuid4

        from rhesis.backend.app import models
        from rhesis.backend.app.constants import TestExecutionContext
        from rhesis.backend.app.schemas.telemetry import OTELSpanCreate, SpanKind, StatusCode

        # Create two different endpoints directly
        endpoint1 = models.Endpoint(
            name="Endpoint Alpha",
            description="First test endpoint",
            connection_type="rest",
            url="https://api.alpha.com",
            environment="production",
            project_id=db_project.id,
            organization_id=test_organization.id,
            user_id=authenticated_user_id,
        )
        test_db.add(endpoint1)

        endpoint2 = models.Endpoint(
            name="Endpoint Beta",
            description="Second test endpoint",
            connection_type="rest",
            url="https://api.beta.com",
            environment="production",
            project_id=db_project.id,
            organization_id=test_organization.id,
            user_id=authenticated_user_id,
        )
        test_db.add(endpoint2)
        test_db.commit()
        test_db.refresh(endpoint1)
        test_db.refresh(endpoint2)

        # Create test entity
        test_entity = models.Test(
            organization_id=test_organization.id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_entity)
        test_db.commit()
        test_db.refresh(test_entity)

        # Create test configurations for each endpoint
        test_config1 = models.TestConfiguration(
            endpoint_id=endpoint1.id,
            organization_id=test_organization.id,
        )
        test_db.add(test_config1)

        test_config2 = models.TestConfiguration(
            endpoint_id=endpoint2.id,
            organization_id=test_organization.id,
        )
        test_db.add(test_config2)
        test_db.commit()
        test_db.refresh(test_config1)
        test_db.refresh(test_config2)

        # Create test runs for each configuration
        test_run1 = models.TestRun(
            test_configuration_id=test_config1.id,
            organization_id=test_organization.id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_run1)

        test_run2 = models.TestRun(
            test_configuration_id=test_config2.id,
            organization_id=test_organization.id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_run2)
        test_db.commit()
        test_db.refresh(test_run1)
        test_db.refresh(test_run2)

        # Create test results for each configuration
        test_result1 = models.TestResult(
            test_run_id=test_run1.id,
            test_id=test_entity.id,
            test_configuration_id=test_config1.id,
            organization_id=test_organization.id,
        )
        test_db.add(test_result1)

        test_result2 = models.TestResult(
            test_run_id=test_run2.id,
            test_id=test_entity.id,
            test_configuration_id=test_config2.id,
            organization_id=test_organization.id,
        )
        test_db.add(test_result2)
        test_db.commit()
        test_db.refresh(test_result1)
        test_db.refresh(test_result2)

        # Create traces for endpoint 1
        trace_id_1a = uuid4().hex
        trace_id_1b = uuid4().hex
        for trace_id in [trace_id_1a, trace_id_1b]:
            span = OTELSpanCreate(
                trace_id=trace_id,
                span_id=uuid4().hex[:16],
                project_id=str(db_project.id),
                environment="production",
                span_name="ai.llm.invoke",
                span_kind=SpanKind.INTERNAL,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                status_code=StatusCode.OK,
                attributes={
                    TestExecutionContext.SpanAttributes.TEST_RUN_ID: str(test_run1.id),
                    TestExecutionContext.SpanAttributes.TEST_ID: str(test_entity.id),
                    TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID: str(test_config1.id),
                },
            )
            stored_spans = create_trace_spans(test_db, [span], str(test_organization.id))
            # Link trace to test result
            stored_spans[0].test_result_id = test_result1.id
            test_db.commit()

        # Create traces for endpoint 2
        trace_id_2a = uuid4().hex
        trace_id_2b = uuid4().hex
        for trace_id in [trace_id_2a, trace_id_2b]:
            span = OTELSpanCreate(
                trace_id=trace_id,
                span_id=uuid4().hex[:16],
                project_id=str(db_project.id),
                environment="production",
                span_name="ai.llm.invoke",
                span_kind=SpanKind.INTERNAL,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                status_code=StatusCode.OK,
                attributes={
                    TestExecutionContext.SpanAttributes.TEST_RUN_ID: str(test_run2.id),
                    TestExecutionContext.SpanAttributes.TEST_ID: str(test_entity.id),
                    TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID: str(test_config2.id),
                },
            )
            stored_spans = create_trace_spans(test_db, [span], str(test_organization.id))
            # Link trace to test result
            stored_spans[0].test_result_id = test_result2.id
            test_db.commit()

        # Test filtering by endpoint 1
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&endpoint_id={endpoint1.id}"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        endpoint1_trace_ids = {t["trace_id"] for t in data["traces"]}

        # Should include traces for endpoint 1
        assert trace_id_1a in endpoint1_trace_ids
        assert trace_id_1b in endpoint1_trace_ids
        # Should NOT include traces for endpoint 2
        assert trace_id_2a not in endpoint1_trace_ids
        assert trace_id_2b not in endpoint1_trace_ids

        # Test filtering by endpoint 2
        response = authenticated_client.get(
            f"/telemetry/traces?project_id={db_project.id}&endpoint_id={endpoint2.id}"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        endpoint2_trace_ids = {t["trace_id"] for t in data["traces"]}

        # Should include traces for endpoint 2
        assert trace_id_2a in endpoint2_trace_ids
        assert trace_id_2b in endpoint2_trace_ids
        # Should NOT include traces for endpoint 1
        assert trace_id_1a not in endpoint2_trace_ids
        assert trace_id_1b not in endpoint2_trace_ids

        # Test without endpoint filter - should include all traces
        response = authenticated_client.get(f"/telemetry/traces?project_id={db_project.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        all_trace_ids = {t["trace_id"] for t in data["traces"]}

        # Should include all traces
        assert trace_id_1a in all_trace_ids
        assert trace_id_1b in all_trace_ids
        assert trace_id_2a in all_trace_ids
        assert trace_id_2b in all_trace_ids


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

        optional_fields = [
            "trace_reviews",
            "last_review",
            "matches_review",
            "review_summary",
            "has_reviews",
        ]
        for field in optional_fields:
            if field in data:
                pass  # Just ensure they are optional but recognized by schema

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

            optional_span_fields = [
                "trace_reviews",
                "last_review",
                "matches_review",
                "review_summary",
            ]
            for field in optional_span_fields:
                if field in span_node:
                    pass

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
        """Test that project_id is optional and defaults to session project scope."""
        response = authenticated_client.get("/telemetry/traces")
        assert response.status_code == status.HTTP_200_OK

        # Should return valid response structure even with no project_id
        data = response.json()
        assert "traces" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_list_traces_all_projects(self, authenticated_client: TestClient):
        """Test that omitting project_id returns valid response structure (fail-closed)."""
        # Query without project_id should work and return valid structure
        response = authenticated_client.get("/telemetry/traces")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        # Should return valid structure even if no traces exist
        assert "traces" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["traces"], list)
        assert isinstance(data["total"], int)
        assert data["total"] >= 0  # Can be 0 if no traces exist

    def test_list_traces_rejects_non_member_project_query_param(
        self, test_db, client, test_org_id, db_project, db_draft_project
    ):
        """Reject project_id query params for projects the caller is not a member of."""
        import uuid

        from rhesis.backend.app.models.project_membership import ProjectMembership
        from tests.backend.fixtures.test_setup import create_test_api_token, create_test_user

        member_user = create_test_user(
            test_db,
            uuid.UUID(test_org_id),
            f"trace-list-member-{uuid.uuid4().hex[:8]}@rhesis-test.com",
            "Trace List Member",
        )
        test_db.add(
            ProjectMembership(
                project_id=db_project.id,
                user_id=member_user.id,
                organization_id=uuid.UUID(test_org_id),
            )
        )
        member_token = create_test_api_token(test_db, member_user, name="Trace list member token")
        test_db.commit()

        spans_data = TraceDataFactory.batch_data(
            count=1, same_trace=False, project_id=str(db_draft_project.id)
        )
        for span_data in spans_data:
            trace_batch = {"spans": [span_data]}
            client.post(
                "/telemetry/traces",
                json=trace_batch,
                headers={"Authorization": f"Bearer {member_token.token}"},
            )

        member_client = TestClient(client.app)
        member_client.headers.update({"Authorization": f"Bearer {member_token.token}"})

        response = member_client.get(f"/telemetry/traces?project_id={db_draft_project.id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "not a member" in response.json()["detail"].lower()

        member_response = member_client.get(f"/telemetry/traces?project_id={db_project.id}")
        assert member_response.status_code == status.HTTP_200_OK

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

        # Query traces
        response = authenticated_client.get(f"/telemetry/traces?project_id={db_project.id}&limit=1")

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


@pytest.mark.security
class TestCrossOrganizationSecurity:
    """🔒 SECURITY: Test multi-tenant isolation for telemetry CRUD and query routes.

    Each test builds two real orgs so the organization_id filtering is exercised
    against an actual second tenant, not just asserted on a single org's rows.
    """

    def test_crud_functions_require_organization_id(self, test_db):
        """🔒 SECURITY: Verify CRUD functions accept and use organization_id parameter"""
        import uuid

        from rhesis.telemetry.schemas import OTELSpan

        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        org, user, _ = create_test_organization_and_user(
            test_db, f"CRUD Org {uuid.uuid4()}", f"crud-{uuid.uuid4()}@test.com", "CRUD User"
        )
        org_id = str(org.id)
        # trace.project_id is a real FK, so the project has to exist
        project = create_project(
            test_db,
            {"name": f"CRUD Project {uuid.uuid4()}", "description": "Test project"},
            organization_id=str(org.id),
            user_id=str(user.id),
        )
        project_id = str(project.id)

        # Create a test trace span using factory
        span_dict = TraceDataFactory.sample_data(project_id=project_id)
        span = OTELSpan(**span_dict)

        # Create spans with organization_id
        spans = create_trace_spans(test_db, [span], org_id)
        assert len(spans) == 1
        assert str(spans[0].organization_id) == org_id
        trace_id = spans[0].trace_id

        # Test get_trace_by_id requires organization_id
        traces = get_trace_by_id(
            test_db, trace_id=trace_id, project_id=project_id, organization_id=org_id
        )
        assert len(traces) == 1
        assert str(traces[0].organization_id) == org_id

        # Test query_traces requires organization_id
        rows = query_traces(test_db, project_id=project_id, organization_id=org_id)
        assert len(rows) >= 1
        # query_traces returns TraceRow(trace, span_count, total)
        assert all(str(row.trace.organization_id) == org_id for row in rows)
        # Total count is embedded in each row via window function
        assert rows[0].total >= 1

    @staticmethod
    def _org_client(test_db, client: TestClient, label: str):
        """Fresh org + owner + project + a client authenticated as that owner.

        Goes through ``create_test_organization_and_user`` rather than building
        the org by hand: the telemetry routes are RBAC-gated, and only that
        helper grants the Owner role a bare ``create_test_user`` leaves off.
        """
        import uuid

        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        suffix = uuid.uuid4()
        org, user, token = create_test_organization_and_user(
            test_db,
            f"Org {label} {suffix}",
            f"user-{label}-{suffix}@test.com".lower(),
            f"User {label}",
        )
        project = create_project(
            test_db,
            {"name": f"Project {label} {suffix}", "description": "Test project"},
            organization_id=str(org.id),
            user_id=str(user.id),
        )

        org_client = TestClient(client.app)
        org_client.headers = {"Authorization": f"Bearer {token.token}"}
        return org_client, project

    def test_cannot_access_trace_from_different_organization(self, test_db, client: TestClient):
        """🔒 SECURITY: Test that users cannot access traces from other organizations"""
        client_a, project_a = self._org_client(test_db, client, "A")
        client_b, _ = self._org_client(test_db, client, "B")

        # Ingest a trace for organization A
        span_data = TraceDataFactory.sample_data(project_id=str(project_a.id))
        response = client_a.post("/telemetry/traces", json={"spans": [span_data]})
        assert response.status_code == 200, response.text
        trace_id = span_data["trace_id"]

        # Organization A should be able to access their trace
        response = client_a.get(f"/telemetry/traces/{trace_id}?project_id={project_a.id}")
        assert response.status_code == 200, response.text
        assert response.json()["trace_id"] == trace_id

        # Organization B should NOT be able to access org A's trace
        response = client_b.get(f"/telemetry/traces/{trace_id}?project_id={project_a.id}")
        assert response.status_code == 404  # Not 403 to avoid information leakage
        assert "not found" in response.json()["detail"].lower()

    def test_list_traces_only_shows_own_organization(self, test_db, client: TestClient):
        """🔒 SECURITY: Test that list endpoint only returns traces from user's organization"""
        client_a, project_a = self._org_client(test_db, client, "A List")
        client_b, project_b = self._org_client(test_db, client, "B List")

        span_a = TraceDataFactory.sample_data(project_id=str(project_a.id))
        assert client_a.post("/telemetry/traces", json={"spans": [span_a]}).status_code == 200

        span_b = TraceDataFactory.sample_data(project_id=str(project_b.id))
        assert client_b.post("/telemetry/traces", json={"spans": [span_b]}).status_code == 200

        # Org A should only see their own traces
        response = client_a.get(f"/telemetry/traces?project_id={project_a.id}")
        assert response.status_code == 200, response.text
        trace_ids = {t["trace_id"] for t in response.json()["traces"]}
        assert span_a["trace_id"] in trace_ids
        assert span_b["trace_id"] not in trace_ids

        # Org B should only see their own traces
        response = client_b.get(f"/telemetry/traces?project_id={project_b.id}")
        assert response.status_code == 200, response.text
        trace_ids = {t["trace_id"] for t in response.json()["traces"]}
        assert span_b["trace_id"] in trace_ids
        assert span_a["trace_id"] not in trace_ids

        # Org A must never see org B's traces, whatever status the cross-org query returns
        response = client_a.get(f"/telemetry/traces?project_id={project_b.id}")
        if response.status_code == 200:
            trace_ids = {t["trace_id"] for t in response.json()["traces"]}
            assert span_b["trace_id"] not in trace_ids

    def test_metrics_only_for_own_organization(self, test_db, client: TestClient):
        """🔒 SECURITY: Test that metrics endpoint only aggregates from user's organization"""
        client_a, project_a = self._org_client(test_db, client, "A Metrics")
        client_b, project_b = self._org_client(test_db, client, "B Metrics")

        for _ in range(3):
            span = TraceDataFactory.sample_data(project_id=str(project_a.id))
            assert client_a.post("/telemetry/traces", json={"spans": [span]}).status_code == 200

        for _ in range(2):
            span = TraceDataFactory.sample_data(project_id=str(project_b.id))
            assert client_b.post("/telemetry/traces", json={"spans": [span]}).status_code == 200

        # Each org's metrics count only its own traces
        response = client_a.get(f"/telemetry/metrics?project_id={project_a.id}")
        assert response.status_code == 200, response.text
        assert response.json()["total_traces"] == 3

        response = client_b.get(f"/telemetry/metrics?project_id={project_b.id}")
        assert response.status_code == 200, response.text
        assert response.json()["total_traces"] == 2


@pytest.mark.integration
class TestTraceTokenAndCostVisibility:
    """Tokens and cost as the trace UI reads them, over the real endpoints.

    The list column, the drawer chips and the project rollup must all report the
    same figure for the same trace -- they used to report three different ones.
    """

    @staticmethod
    def _span(trace_id, span_id, project_id, *, parent=None, operation, tokens=None):
        now = datetime.now(timezone.utc)
        attributes = {"ai.operation.type": operation}
        if tokens is not None:
            attributes["ai.model.name"] = "gpt-4"
            attributes["ai.llm.tokens.input"] = tokens[0]
            attributes["ai.llm.tokens.output"] = tokens[1]
            attributes["ai.llm.tokens.total"] = tokens[2]
        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent,
            "project_id": project_id,
            "environment": "development",
            "span_name": "ai.llm.invoke" if operation == "llm.invoke" else "ai.agent.invoke",
            "span_kind": "CLIENT",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(milliseconds=250)).isoformat(),
            "status_code": "OK",
            "attributes": attributes,
            "events": [],
            "links": [],
            "resource": {},
        }

    @staticmethod
    def _summary(client, project_id, trace_id):
        response = client.get(f"/telemetry/traces?project_id={project_id}&limit=100")
        assert response.status_code == status.HTTP_200_OK
        for trace in response.json()["traces"]:
            if trace["trace_id"] == trace_id:
                return trace
        raise AssertionError(f"trace {trace_id} missing from the list response")

    def _ingest(self, client, spans):
        response = client.post("/telemetry/traces", json={"spans": spans})
        assert response.status_code == status.HTTP_200_OK

    def test_pydantic_ai_run_is_not_double_counted(
        self, authenticated_client: TestClient, db_project
    ):
        """The agent-run span repeats its children's aggregate under the same keys.

        Summing every span would report 840; only the llm.invoke spans count.
        """
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        agent_span = uuid.uuid4().hex[:16]
        spans = [
            self._span(
                trace_id, agent_span, project_id, operation="agent.invoke", tokens=(300, 120, 420)
            ),
            self._span(
                trace_id,
                uuid.uuid4().hex[:16],
                project_id,
                parent=agent_span,
                operation="llm.invoke",
                tokens=(100, 50, 150),
            ),
            self._span(
                trace_id,
                uuid.uuid4().hex[:16],
                project_id,
                parent=agent_span,
                operation="llm.invoke",
                tokens=(200, 70, 270),
            ),
        ]
        self._ingest(authenticated_client, spans)

        response = authenticated_client.get(f"/telemetry/traces/{trace_id}?project_id={project_id}")
        assert response.status_code == status.HTTP_200_OK
        detail = response.json()

        assert detail["total_tokens"] == 420
        assert detail["total_input_tokens"] == 300
        assert detail["total_output_tokens"] == 120

    def test_list_and_detail_report_the_same_tokens(
        self, authenticated_client: TestClient, db_project
    ):
        """The core bug: the list read the root span alone and so showed 0."""
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        agent_span = uuid.uuid4().hex[:16]
        spans = [
            # A root span with no token attributes at all -- the usual shape, and
            # what the list used to read its figure from.
            self._span(trace_id, agent_span, project_id, operation="agent.invoke"),
            self._span(
                trace_id,
                uuid.uuid4().hex[:16],
                project_id,
                parent=agent_span,
                operation="llm.invoke",
                tokens=(100, 50, 150),
            ),
            self._span(
                trace_id,
                uuid.uuid4().hex[:16],
                project_id,
                parent=agent_span,
                operation="llm.invoke",
                tokens=(200, 70, 270),
            ),
        ]
        self._ingest(authenticated_client, spans)

        detail = authenticated_client.get(
            f"/telemetry/traces/{trace_id}?project_id={project_id}"
        ).json()
        summary = self._summary(authenticated_client, project_id, trace_id)

        assert detail["total_tokens"] == 420
        assert summary["total_tokens"] == detail["total_tokens"]

    def test_reported_total_survives_the_round_trip(
        self, authenticated_client: TestClient, db_project
    ):
        """Google ADK folds cache-read tokens into its total, so it exceeds in + out."""
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        self._ingest(
            authenticated_client,
            [
                self._span(
                    trace_id,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(100, 50, 950),
                )
            ],
        )

        detail = authenticated_client.get(
            f"/telemetry/traces/{trace_id}?project_id={project_id}"
        ).json()

        assert detail["total_tokens"] == 950
        assert self._summary(authenticated_client, project_id, trace_id)["total_tokens"] == 950

    def test_trace_with_no_llm_spans_omits_tokens(
        self, authenticated_client: TestClient, db_project
    ):
        """The list sends null so the column shows an em dash rather than a 0."""
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        self._ingest(
            authenticated_client,
            [self._span(trace_id, uuid.uuid4().hex[:16], project_id, operation="tool.invoke")],
        )

        detail = authenticated_client.get(
            f"/telemetry/traces/{trace_id}?project_id={project_id}"
        ).json()

        assert detail["total_tokens"] == 0
        assert self._summary(authenticated_client, project_id, trace_id)["total_tokens"] is None

    def test_span_nodes_expose_cost_once_enriched(
        self, authenticated_client: TestClient, db_project, test_db, test_org_id
    ):
        """Per-span cost reaches the Span Details panel, and only for priced spans."""
        from rhesis.backend.app.crud.telemetry import mark_trace_processed

        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        agent_span = uuid.uuid4().hex[:16]
        llm_span = uuid.uuid4().hex[:16]
        self._ingest(
            authenticated_client,
            [
                self._span(
                    trace_id,
                    agent_span,
                    project_id,
                    operation="agent.invoke",
                    tokens=(100, 50, 150),
                ),
                self._span(
                    trace_id,
                    llm_span,
                    project_id,
                    parent=agent_span,
                    operation="llm.invoke",
                    tokens=(100, 50, 150),
                ),
            ],
        )

        # Stand in for the async enrichment job, which does not run in tests.
        mark_trace_processed(
            test_db,
            trace_id,
            {
                "costs": {
                    "total_cost_usd": 0.006,
                    "total_cost_eur": 0.0054,
                    "total_input_tokens": 100,
                    "total_output_tokens": 50,
                    "total_tokens": 150,
                    "breakdown": [
                        {
                            "span_id": llm_span,
                            "model_name": "gpt-4",
                            "input_tokens": 100,
                            "output_tokens": 50,
                            "total_tokens": 150,
                            "input_cost_usd": 0.003,
                            "output_cost_usd": 0.003,
                            "total_cost_usd": 0.006,
                            "input_cost_eur": 0.0027,
                            "output_cost_eur": 0.0027,
                            "total_cost_eur": 0.0054,
                        }
                    ],
                }
            },
        )

        detail = authenticated_client.get(
            f"/telemetry/traces/{trace_id}?project_id={project_id}"
        ).json()

        def walk(nodes):
            for node in nodes:
                yield node
                yield from walk(node["children"])

        by_span = {node["span_id"]: node for node in walk(detail["root_spans"])}

        assert detail["total_cost_usd"] == pytest.approx(0.006)
        assert by_span[llm_span]["cost_usd"] == pytest.approx(0.006)
        assert by_span[llm_span]["model_name"] == "gpt-4"
        # The agent-run span is never priced, so it shows no Usage cost.
        assert by_span[agent_span]["cost_usd"] is None
        assert by_span[agent_span]["model_name"] is None
