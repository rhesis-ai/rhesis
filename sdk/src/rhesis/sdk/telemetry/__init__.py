"""OpenTelemetry telemetry module - complete tracing infrastructure."""

# Core tracing API
# Helpers
from rhesis.sdk.telemetry.attributes import (
    AIAttributes,
    AIEvents,
    create_llm_attributes,
    create_tool_attributes,
    validate_span_name,
)

# Infrastructure
from rhesis.sdk.telemetry.provider import get_tracer_provider, shutdown_tracer_provider

# Schemas (for backend to import)
from rhesis.sdk.telemetry.schemas import (
    AILLMAttributes,
    AIOperationType,
    AIToolAttributes,
    OTELSpan,
    OTELTraceBatch,
    SpanEvent,
    SpanKind,
    SpanLink,
    StatusCode,
    TraceIngestResponse,
)
from rhesis.sdk.telemetry.tracer import Tracer

__all__ = [
    # Primary API
    "Tracer",
    # Schemas
    "SpanKind",
    "StatusCode",
    "AIOperationType",
    "OTELSpan",
    "OTELTraceBatch",
    "TraceIngestResponse",
    "SpanEvent",
    "SpanLink",
    "AILLMAttributes",
    "AIToolAttributes",
    # Infrastructure
    "get_tracer_provider",
    "shutdown_tracer_provider",
    # Helpers
    "AIAttributes",
    "AIEvents",
    "create_llm_attributes",
    "create_tool_attributes",
    "validate_span_name",
]
