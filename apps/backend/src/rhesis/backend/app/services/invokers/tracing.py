"""Trace creation for REST/WebSocket endpoint invocations."""

import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.constants import TestExecutionContext as TestContextConstants
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.schemas.test_execution import TestExecutionContext
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

    # Test context - use constants from TestContextConstants.SpanAttributes
    TEST_RUN_ID = TestContextConstants.SpanAttributes.TEST_RUN_ID
    TEST_RESULT_ID = TestContextConstants.SpanAttributes.TEST_RESULT_ID
    TEST_ID = TestContextConstants.SpanAttributes.TEST_ID
    TEST_CONFIGURATION_ID = TestContextConstants.SpanAttributes.TEST_CONFIGURATION_ID


def generate_trace_id() -> str:
    """Generate OTEL trace ID (32 hex chars)."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Generate OTEL span ID (16 hex chars)."""
    return secrets.token_hex(8)


def create_endpoint_attributes(
    endpoint: Endpoint, test_execution_context: Optional[Dict[str, str]] = None, **kwargs
) -> Dict[str, Any]:
    """
    Create standard attributes for endpoint invocations.

    Args:
        endpoint: Endpoint model
        test_execution_context: Optional test execution IDs (test_run_id, test_result_id, etc.)
        **kwargs: Additional attributes (e.g., request_size, response_data)

    Returns:
        Dictionary of attributes following semantic conventions
    """
    attrs = {
        EndpointAttributes.ENDPOINT_ID: str(endpoint.id),
        EndpointAttributes.ENDPOINT_NAME: endpoint.name,
        EndpointAttributes.ENDPOINT_TYPE: endpoint.connection_type,
        EndpointAttributes.ENDPOINT_URL: endpoint.url,
    }

    # Add test context attributes if available
    if test_execution_context:
        # Validate and ensure proper types
        context = TestExecutionContext(**test_execution_context)
        attrs[EndpointAttributes.TEST_RUN_ID] = str(context.test_run_id)
        attrs[EndpointAttributes.TEST_ID] = str(context.test_id)
        attrs[EndpointAttributes.TEST_CONFIGURATION_ID] = str(context.test_configuration_id)
        if context.test_result_id:
            attrs[EndpointAttributes.TEST_RESULT_ID] = str(context.test_result_id)

    # Add method for REST endpoints
    if hasattr(endpoint, "method") and endpoint.method:
        attrs[EndpointAttributes.ENDPOINT_METHOD] = endpoint.method

    # Add any additional attributes
    attrs.update(kwargs)
    return attrs


@asynccontextmanager
async def create_invocation_trace(
    db: Session,
    endpoint: Endpoint,
    organization_id: str,
    test_execution_context: Optional[Dict[str, str]] = None,
):
    """
    Create a trace span for REST/WebSocket invocations.

    Uses OTELSpan class and semantic conventions from SDK.
    This creates an invocation trace that captures the endpoint call
    with timing, status, and optional test execution context.

    Args:
        db: Database session
        endpoint: Endpoint model
        organization_id: Organization ID
        test_execution_context: Optional dict with test_run_id, test_result_id, test_id,
            test_configuration_id (only present during test execution)

    Yields:
        Dict that executor can update with result data

    Example:
        async with create_invocation_trace(db, endpoint, org_id, context) as trace_ctx:
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
        # Skip trace creation if endpoint has no project_id
        if endpoint.project_id is None:
            logger.debug(
                f"Skipping trace creation for endpoint {endpoint.id} - no project_id assigned"
            )
            return

        end_time = datetime.now(timezone.utc)
        result = trace_context.get("result")
        error = trace_context.get("error")

        # Normalize result to dict if it's a Pydantic model
        if result and hasattr(result, "model_dump"):
            result = result.model_dump(exclude_none=True)

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
            span_name=f"function.endpoint_{endpoint.connection_type.lower()}_invoke",
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

        # Store span and trigger enrichment
        from rhesis.backend.app.services.telemetry.enrichment import EnrichmentService

        enrichment_service = EnrichmentService(db)
        stored_spans, _, _ = enrichment_service.create_and_enrich_spans(
            spans=[otel_span],
            organization_id=organization_id,
            project_id=str(endpoint.project_id),
        )

        if stored_spans:
            logger.debug(f"Created and enriched invocation trace {stored_spans[0].trace_id}")
