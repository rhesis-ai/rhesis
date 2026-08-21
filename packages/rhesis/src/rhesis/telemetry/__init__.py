"""Lightweight OpenTelemetry telemetry for the Rhesis platform."""

from rhesis.telemetry.attributes import (
    MAX_CONTENT_LENGTH,
    AIAttributes,
    AIEvents,
    create_llm_attributes,
    create_tool_attributes,
    validate_span_name,
)
from rhesis.telemetry.context import (
    get_conversation_id,
    get_conversation_mapped_input,
    get_conversation_trace_id,
    get_root_trace_id,
    get_test_execution_context,
    is_llm_observation_active,
    is_tracing_disabled,
    set_conversation_id,
    set_conversation_mapped_input,
    set_conversation_trace_id,
    set_llm_observation_active,
    set_root_trace_id,
    set_test_execution_context,
    set_tracing_disabled,
)
from rhesis.telemetry.conversation import (
    DEFAULT_TURN_SPAN_NAME,
    ConversationTurn,
    build_conversation_parent_context,
    conversation_turn,
)
from rhesis.telemetry.exporter import RhesisOTLPExporter
from rhesis.telemetry.provider import (
    build_tracer_provider,
    get_tracer_provider,
    shutdown_tracer_provider,
)
from rhesis.telemetry.schemas import (
    OTELSpan,
    OTELTraceBatch,
    SpanEvent,
    SpanKind,
    SpanLink,
    StatusCode,
)
from rhesis.telemetry.token_extraction import extract_token_usage, get_first_value

__all__ = [
    "RhesisOTLPExporter",
    "build_tracer_provider",
    "get_tracer_provider",
    "shutdown_tracer_provider",
    "OTELSpan",
    "OTELTraceBatch",
    "SpanEvent",
    "SpanKind",
    "SpanLink",
    "StatusCode",
    # Semantic conventions
    "MAX_CONTENT_LENGTH",
    "AIAttributes",
    "AIEvents",
    "create_llm_attributes",
    "create_tool_attributes",
    "validate_span_name",
    # Conversation turns
    "DEFAULT_TURN_SPAN_NAME",
    "ConversationTurn",
    "build_conversation_parent_context",
    "conversation_turn",
    # Context
    "get_conversation_id",
    "get_conversation_mapped_input",
    "get_conversation_trace_id",
    "get_root_trace_id",
    "get_test_execution_context",
    "is_llm_observation_active",
    "is_tracing_disabled",
    "set_conversation_id",
    "set_conversation_mapped_input",
    "set_conversation_trace_id",
    "set_llm_observation_active",
    "set_root_trace_id",
    "set_test_execution_context",
    "set_tracing_disabled",
    # Token usage
    "extract_token_usage",
    "get_first_value",
]
