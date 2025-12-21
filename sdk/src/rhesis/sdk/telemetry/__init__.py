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

# Auto-instrumentation
from rhesis.sdk.telemetry.observer import auto_instrument, disable_auto_instrument

# Infrastructure
from rhesis.sdk.telemetry.provider import get_tracer_provider, shutdown_tracer_provider

# Schemas (for backend to import)
from rhesis.sdk.telemetry.schemas import (
    FORBIDDEN_SPAN_DOMAINS,
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
    # Auto-instrumentation
    "auto_instrument",
    "disable_auto_instrument",
    # Primary API
    "Tracer",
    # Schemas
    "SpanKind",
    "StatusCode",
    "AIOperationType",
    "FORBIDDEN_SPAN_DOMAINS",
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
