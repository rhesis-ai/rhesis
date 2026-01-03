"""Canonical Pydantic schemas for OpenTelemetry traces."""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TestExecutionContext(TypedDict, total=False):
    """
    Test execution context passed from backend to SDK.

    This context is injected into function kwargs during test execution
    and extracted by the tracing layer to link spans to test runs.

    All IDs are UUID strings in the standard format:
    '550e8400-e29b-41d4-a716-446655440000'

    Note: Received as strings (serialized UUIDs) from backend.
    """

    test_run_id: str  # UUID string
    test_id: str  # UUID string
    test_configuration_id: str  # UUID string
    test_result_id: Optional[str]  # UUID string or None


# Semantic Layer Constants

# Forbidden framework concepts (not primitive operations)
# These should NOT appear as domains in span names (ai.<domain>.<action>)
FORBIDDEN_SPAN_DOMAINS: List[str] = ["agent", "chain", "workflow", "pipeline"]


class SpanKind(str, Enum):
    """OpenTelemetry span kinds."""

    INTERNAL = "INTERNAL"
    CLIENT = "CLIENT"
    SERVER = "SERVER"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class StatusCode(str, Enum):
    """OpenTelemetry status codes."""

    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


class AIOperationType(str, Enum):
    """
    AI operation types (primitive operations only).

    These represent atomic operations, NOT framework concepts.
    Following semantic convention: ai.<domain>.<action>

    Valid: llm, tool, retrieval, embedding, rerank, evaluation, guardrail, transform
    (primitive operations)
    Invalid: agent, chain, workflow, pipeline (framework concepts)
    """

    LLM_INVOKE = "ai.llm.invoke"
    TOOL_INVOKE = "ai.tool.invoke"
    RETRIEVAL = "ai.retrieval"
    EMBEDDING_GENERATE = "ai.embedding.generate"
    RERANK = "ai.rerank"
    EVALUATION = "ai.evaluation"
    GUARDRAIL = "ai.guardrail"
    TRANSFORM = "ai.transform"


class SpanEvent(BaseModel):
    """Span event (e.g., ai.prompt, ai.completion)."""

    name: str = Field(..., description="Event name")
    timestamp: datetime = Field(..., description="Event timestamp")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Event attributes")


class SpanLink(BaseModel):
    """Link to another span."""

    trace_id: str = Field(..., description="32-char hex trace ID")
    span_id: str = Field(..., description="16-char hex span ID")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Link attributes")


class OTELSpan(BaseModel):
    """
    Canonical OpenTelemetry span model.
    This is the source of truth - backend imports this schema.
    """

    # OTEL identifiers
    trace_id: str = Field(..., description="32-char hex trace ID")
    span_id: str = Field(..., description="16-char hex span ID")
    parent_span_id: Optional[str] = Field(None, description="16-char hex parent span ID")

    # Rhesis context
    project_id: Optional[str] = Field(None, description="Rhesis project ID")
    environment: str = Field("development", description="Environment name")

    # Span metadata
    span_name: str = Field(
        ...,
        description="Semantic: ai.<domain>.<action> or function.<name>",
    )
    span_kind: SpanKind = Field(SpanKind.INTERNAL, description="Span kind")

    # Timing
    start_time: datetime = Field(..., description="Span start time (UTC)")
    end_time: datetime = Field(..., description="Span end time (UTC)")

    # Status
    status_code: StatusCode = Field(StatusCode.OK, description="Span status")
    status_message: Optional[str] = Field(None, description="Error message if failed")

    # Flexible data
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Span attributes")
    events: List[SpanEvent] = Field(default_factory=list, description="Span events")
    links: List[SpanLink] = Field(default_factory=list, description="Span links")
    resource: Dict[str, Any] = Field(default_factory=dict, description="Resource attributes")

    @field_validator("trace_id")
    @classmethod
    def validate_trace_id(cls, v: str) -> str:
        """Validate trace ID format (32-char hex)."""
        if len(v) != 32 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("trace_id must be 32-character hex string")
        return v.lower()

    @field_validator("span_id", "parent_span_id")
    @classmethod
    def validate_span_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate span ID format (16-char hex)."""
        if v is None:
            return v
        if len(v) != 16 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("span_id must be 16-character hex string")
        return v.lower()

    @field_validator("span_name")
    @classmethod
    def validate_span_name(cls, v: str) -> str:
        """
        Validate span name follows semantic conventions.

        Allowed patterns:
        - ai.<domain>.<action> (e.g., ai.llm.invoke, ai.tool.invoke)
        - function.<name> (for generic functions)

        Forbidden: Framework concepts (agent, chain, workflow, pipeline)
        """
        # Allow function.* pattern for generic functions
        if v.startswith("function."):
            return v

        # Validate ai.* pattern
        pattern = r"^ai\.[a-z]+(\.[a-z]+)?$"
        if not re.match(pattern, v):
            raise ValueError(
                f"span_name must follow 'ai.<domain>.<action>' or 'function.<name>' (got: {v}). "
                "Examples: 'ai.llm.invoke', 'ai.tool.invoke', 'function.process_data'"
            )

        # Reject framework concepts
        parts = v.split(".")
        if len(parts) >= 2 and parts[1] in FORBIDDEN_SPAN_DOMAINS:
            raise ValueError(
                f"span_name cannot use framework concept '{parts[1]}'. "
                "Use primitive operations: llm, tool, retrieval, embedding"
            )

        return v

    @field_validator("end_time")
    @classmethod
    def validate_timing(cls, v: datetime, info) -> datetime:
        """Ensure end_time > start_time."""
        if "start_time" in info.data and v < info.data["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v


class OTELTraceBatch(BaseModel):
    """Batch of spans for ingestion."""

    spans: List[OTELSpan] = Field(..., min_length=1, max_length=1000)


class TraceIngestResponse(BaseModel):
    """Response from backend after trace ingestion."""

    status: str = Field("received", description="Ingestion status")
    span_count: int = Field(..., description="Number of spans received")
    trace_id: str = Field(..., description="Trace ID")


# AI-specific attribute models for type safety
class AILLMAttributes(BaseModel):
    """Type-safe LLM attributes."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    operation_type: str = Field("llm.invoke", alias="ai.operation.type")
    model_provider: str = Field(..., alias="ai.model.provider")
    model_name: str = Field(..., alias="ai.model.name")
    tokens_input: Optional[int] = Field(None, alias="ai.llm.tokens.input")
    tokens_output: Optional[int] = Field(None, alias="ai.llm.tokens.output")
    tokens_total: Optional[int] = Field(None, alias="ai.llm.tokens.total")


class AIToolAttributes(BaseModel):
    """Type-safe tool attributes."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    operation_type: str = Field("tool.invoke", alias="ai.operation.type")
    tool_name: str = Field(..., alias="ai.tool.name")
    tool_type: str = Field(..., alias="ai.tool.type")
