"""Manual trace creation for REST/WebSocket endpoint invocations."""

import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.sdk.telemetry.schemas import OTELSpan, SpanKind, StatusCode

logger = logging.getLogger(__name__)


class EndpointAttributes:
    """
    Semantic attributes for endpoint invocations.

    Following OpenTelemetry semantic conventions with custom endpoint namespace.
    """

    # Endpoint metadata
    ENDPOINT_ID = "endpoint.id"
    ENDPOINT_NAME = "endpoint.name"
    ENDPOINT_TYPE = "endpoint.type"
    ENDPOINT_URL = "endpoint.url"
    ENDPOINT_METHOD = "endpoint.method"  # For REST

    # Request/response
    REQUEST_SIZE = "endpoint.request.size"
    RESPONSE_SIZE = "endpoint.response.size"
    RESPONSE_STATUS = "endpoint.response.status"
    RESPONSE_HAS_OUTPUT = "endpoint.response.has_output"
    RESPONSE_OUTPUT_PREVIEW = "endpoint.response.output_preview"

    # Test context (following rhesis.test.* convention)
    TEST_RUN_ID = "rhesis.test.run_id"
    TEST_RESULT_ID = "rhesis.test.result_id"
    TEST_ID = "rhesis.test.id"
    TEST_CONFIGURATION_ID = "rhesis.test.configuration_id"


def generate_trace_id() -> str:
    """Generate OTEL trace ID (32 hex chars)."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Generate OTEL span ID (16 hex chars)."""
    return secrets.token_hex(8)


def create_endpoint_attributes(
    endpoint: Endpoint, test_execution_context: Dict[str, str], **kwargs
) -> Dict[str, Any]:
    """
    Create standard attributes for endpoint invocations.

    Args:
        endpoint: Endpoint model
        test_execution_context: Test execution IDs (test_run_id, test_result_id, etc.)
        **kwargs: Additional attributes (e.g., request_size, response_data)

    Returns:
        Dictionary of attributes following semantic conventions
    """
    attrs = {
        EndpointAttributes.ENDPOINT_ID: str(endpoint.id),
        EndpointAttributes.ENDPOINT_NAME: endpoint.name,
        EndpointAttributes.ENDPOINT_TYPE: endpoint.connection_type,
        EndpointAttributes.ENDPOINT_URL: endpoint.url,
        # Test context
        EndpointAttributes.TEST_RUN_ID: test_execution_context.get("test_run_id"),
        EndpointAttributes.TEST_RESULT_ID: test_execution_context.get("test_result_id"),
        EndpointAttributes.TEST_ID: test_execution_context.get("test_id"),
        EndpointAttributes.TEST_CONFIGURATION_ID: test_execution_context.get(
            "test_configuration_id"
        ),
    }

    # Add method for REST endpoints
    if hasattr(endpoint, "method") and endpoint.method:
        attrs[EndpointAttributes.ENDPOINT_METHOD] = endpoint.method

    # Add any additional attributes
    attrs.update(kwargs)
    return attrs


@asynccontextmanager
async def create_manual_invocation_trace(
    db: Session, endpoint: Endpoint, test_execution_context: Dict[str, str], organization_id: str
):
    """
    Create a manual trace span for REST/WebSocket invocations.

    Uses OTELSpan class and semantic conventions from SDK.
    This creates a simple invocation trace that captures the endpoint call
    with timing, status, and test execution context.

    Args:
        db: Database session
        endpoint: Endpoint model
        test_execution_context: Dict with test_run_id, test_result_id, test_id,
            test_configuration_id
        organization_id: Organization ID

    Yields:
        Dict that executor can update with result data

    Example:
        async with create_manual_invocation_trace(db, endpoint, context, org_id) as trace_ctx:
            result = await invoker.invoke(...)
            trace_ctx["result"] = result
    """
    trace_id = generate_trace_id()
    span_id = generate_span_id()
    start_time = datetime.now(timezone.utc)

    # Create base attributes
    attributes = create_endpoint_attributes(endpoint, test_execution_context)

    # Context for executor to add result data
    trace_context = {
        "result": None,
        "error": None,
    }

    try:
        yield trace_context  # Executor runs invocation and sets result/error
    except Exception as e:
        trace_context["error"] = e
        raise
    finally:
        end_time = datetime.now(timezone.utc)
        result = trace_context.get("result")
        error = trace_context.get("error")

        # Add result metadata to attributes
        if result:
            attributes[EndpointAttributes.RESPONSE_STATUS] = result.get("status", "unknown")
            attributes[EndpointAttributes.RESPONSE_HAS_OUTPUT] = result.get("output") is not None

            # Truncate output for storage
            output = result.get("output")
            if output:
                output_preview = str(output)[:1000]
                attributes[EndpointAttributes.RESPONSE_OUTPUT_PREVIEW] = output_preview
                attributes[EndpointAttributes.RESPONSE_SIZE] = len(str(output))

        # Create OTELSpan using SDK schema
        # Span name follows function.* pattern for generic functions
        otel_span = OTELSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            project_id=str(endpoint.project_id),
            environment=endpoint.environment or "development",
            span_name=f"function.endpoint_{endpoint.connection_type}_invoke",
            span_kind=SpanKind.CLIENT,  # Calling external service
            start_time=start_time,
            end_time=end_time,
            status_code=StatusCode.ERROR if error else StatusCode.OK,
            status_message=str(error) if error else None,
            attributes=attributes,
            events=[],
            links=[],
            resource={},
        )

        # Store span in database
        stored_spans = crud.create_trace_spans(db, [otel_span], organization_id)

        # Trigger enrichment for the trace (same as SDK traces)
        if stored_spans:
            from rhesis.backend.app.services.telemetry.enrichment_service import EnrichmentService

            trace_id = stored_spans[0].trace_id
            project_id = str(endpoint.project_id)
            enrichment_service = EnrichmentService(db)
            enrichment_service.enqueue_enrichment(trace_id, project_id)
            logger.debug(f"Triggered enrichment for manual trace {trace_id}")
