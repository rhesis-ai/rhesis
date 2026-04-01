"""Trace creation for REST/WebSocket endpoint invocations."""

import base64
import json
import logging
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.constants import TestExecutionContext as TestContextConstants
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.schemas.test_execution import TestExecutionContext
from rhesis.sdk.telemetry.constants import ConversationContext as ConversationConstants
from rhesis.sdk.telemetry.schemas import OTELSpan, SpanKind, StatusCode

logger = logging.getLogger(__name__)


@dataclass
class DeferredTraceData:
    """In-memory trace data collected during deferred mode, written later."""

    otel_span: OTELSpan
    trace_id: str
    project_id: str
    organization_id: str
    conversation_id: Optional[str] = None
    file_data: Optional[List[Dict[str, Any]]] = None
    first_turn_link: Optional[Dict[str, str]] = field(default=None)


def persist_deferred_trace(db: Session, trace_data: DeferredTraceData) -> None:
    """Write a DeferredTraceData to DB using a live session."""
    from rhesis.backend.app.services.telemetry.enrichment import EnrichmentService

    enrichment_service = EnrichmentService(db)
    stored_spans, _, _ = enrichment_service.create_and_enrich_spans(
        spans=[trace_data.otel_span],
        organization_id=trace_data.organization_id,
        project_id=trace_data.project_id,
    )

    if stored_spans and trace_data.file_data:
        _store_trace_files(
            db=db,
            trace_id=stored_spans[0].id,
            files=trace_data.file_data,
            organization_id=trace_data.organization_id,
        )

    if trace_data.first_turn_link and stored_spans:
        from rhesis.backend.app.services.endpoint.service import EndpointService

        EndpointService._link_first_turn_trace(
            db=db,
            trace_id=trace_data.first_turn_link["trace_id"],
            conversation_id=trace_data.first_turn_link["conversation_id"],
            organization_id=trace_data.organization_id,
        )


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

    # Conversation I/O - use constants from ConversationConstants.SpanAttributes
    CONVERSATION_INPUT = ConversationConstants.SpanAttributes.CONVERSATION_INPUT
    CONVERSATION_OUTPUT = ConversationConstants.SpanAttributes.CONVERSATION_OUTPUT


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
    db: Optional[Session],
    endpoint: Endpoint,
    organization_id: str,
    test_execution_context: Optional[Dict[str, str]] = None,
    conversation_id: Optional[str] = None,
    input_data: Optional[Dict] = None,
    deferred: bool = False,
    trace_id: Optional[str] = None,
):
    """
    Create a trace span for REST/WebSocket invocations.

    Args:
        db: Database session (can be None when deferred=True)
        endpoint: Endpoint model
        organization_id: Organization ID
        test_execution_context: Optional test execution IDs
        conversation_id: Optional conversation ID for multi-turn traces
        input_data: Optional input data dict for capturing mapped I/O
        deferred: When True, collect trace data in-memory instead of writing to DB.
            The DeferredTraceData is stored in trace_context["_deferred_trace"].
        trace_id: When provided, reuse this trace_id instead of looking up from DB
            (used for in-memory trace tracking across multi-turn conversations).

    Yields:
        Dict that executor can update with result data
    """
    from rhesis.backend.app import crud

    existing_trace_id = trace_id
    if not existing_trace_id and conversation_id and endpoint.project_id and db:
        existing_trace_id = crud.get_trace_id_for_conversation(
            db=db,
            conversation_id=conversation_id,
            project_id=str(endpoint.project_id),
            organization_id=organization_id,
        )

        if existing_trace_id is None:
            from rhesis.backend.app.services.telemetry.conversation_linking import (
                get_trace_id_from_pending_links,
            )

            existing_trace_id = get_trace_id_from_pending_links(conversation_id)
            if existing_trace_id:
                logger.debug(f"Found trace_id from pending links cache: {existing_trace_id}")

    final_trace_id = existing_trace_id or generate_trace_id()
    span_id = generate_span_id()
    start_time = datetime.now(timezone.utc)

    attributes = create_endpoint_attributes(endpoint, test_execution_context)

    trace_context: Dict[str, Any] = {
        "result": None,
        "error": None,
    }

    try:
        yield trace_context
    except Exception as e:
        trace_context["error"] = e
        raise
    finally:
        if endpoint.project_id is None:
            logger.debug(
                f"Skipping trace creation for endpoint {endpoint.id} - no project_id assigned"
            )
            return

        end_time = datetime.now(timezone.utc)
        result = trace_context.get("result")
        error = trace_context.get("error")

        if result is not None and isinstance(result, dict):
            result["trace_id"] = final_trace_id

        if result and hasattr(result, "model_dump"):
            result = result.model_dump(exclude_none=True)

        if result:
            attributes[EndpointAttributes.RESPONSE_STATUS] = result.get("status", "unknown")
            attributes[EndpointAttributes.RESPONSE_HAS_OUTPUT] = result.get("output") is not None

            output = result.get("output")
            if output:
                output_str = json.dumps(output) if isinstance(output, (dict, list)) else str(output)
                attributes[EndpointAttributes.RESPONSE_OUTPUT_PREVIEW] = output_str[:1000]
                attributes[EndpointAttributes.RESPONSE_SIZE] = len(output_str)

        if input_data:
            mapped_input = str(input_data.get("input", ""))
            if mapped_input:
                attributes[EndpointAttributes.CONVERSATION_INPUT] = mapped_input[
                    : ConversationConstants.MAX_IO_LENGTH
                ]
        if result and isinstance(result, dict):
            raw_output = result.get("output", "")
            mapped_output = (
                json.dumps(raw_output) if isinstance(raw_output, (dict, list)) else str(raw_output)
            )
            if mapped_output:
                attributes[EndpointAttributes.CONVERSATION_OUTPUT] = mapped_output[
                    : ConversationConstants.MAX_IO_LENGTH
                ]

        otel_span = OTELSpan(
            trace_id=final_trace_id,
            span_id=span_id,
            parent_span_id=None,
            project_id=str(endpoint.project_id),
            environment=endpoint.environment or "development",
            conversation_id=conversation_id,
            span_name=f"function.endpoint_{endpoint.connection_type.lower()}_invoke",
            span_kind=SpanKind.CLIENT,
            start_time=start_time,
            end_time=end_time,
            status_code=StatusCode.ERROR if error else StatusCode.OK,
            status_message=str(error) if error else None,
            attributes=attributes,
            events=[],
            links=[],
            resource={},
        )

        if deferred:
            file_data = input_data.get("files") if input_data else None
            deferred_data = DeferredTraceData(
                otel_span=otel_span,
                trace_id=final_trace_id,
                project_id=str(endpoint.project_id),
                organization_id=organization_id,
                conversation_id=conversation_id,
                file_data=file_data,
            )
            trace_context["_deferred_trace"] = deferred_data
            logger.debug(f"Deferred invocation trace {final_trace_id} (will persist later)")
        else:
            from rhesis.backend.app.services.telemetry.enrichment import EnrichmentService

            enrichment_service = EnrichmentService(db)
            stored_spans, _, _ = enrichment_service.create_and_enrich_spans(
                spans=[otel_span],
                organization_id=organization_id,
                project_id=str(endpoint.project_id),
            )

            if stored_spans:
                logger.debug(f"Created and enriched invocation trace {stored_spans[0].trace_id}")

                files = input_data.get("files") if input_data else None
                if files:
                    _store_trace_files(
                        db=db,
                        trace_id=stored_spans[0].id,
                        files=files,
                        organization_id=organization_id,
                    )


def _store_trace_files(
    db: Session,
    trace_id: UUID,
    files: List[Dict[str, Any]],
    organization_id: str,
) -> None:
    """Store input files as File records linked to a Trace.

    Each item in files should have:
    - data: base64-encoded file content
    - filename: original filename
    - content_type: MIME type
    """
    from rhesis.backend.app import crud, schemas

    for idx, file_data in enumerate(files):
        if not isinstance(file_data, dict):
            continue

        content_b64 = file_data.get("data")
        if not content_b64:
            continue

        try:
            content = base64.b64decode(content_b64)
        except Exception:
            logger.warning(f"Failed to decode base64 for trace file {idx}")
            continue

        file_create = schemas.FileCreate(
            filename=file_data.get("filename", f"file_{idx}"),
            content_type=file_data.get("content_type", "application/octet-stream"),
            size_bytes=len(content),
            content=content,
            entity_id=trace_id,
            entity_type="Trace",
            position=idx,
        )
        crud.create_file(db, file_create, organization_id=organization_id)

    logger.debug(f"Stored {len(files)} input file(s) for trace_id={trace_id}")
