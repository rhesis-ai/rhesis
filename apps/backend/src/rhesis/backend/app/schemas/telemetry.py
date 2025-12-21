"""Pydantic schemas for OpenTelemetry traces."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# Enums
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
    """AI-specific operation types."""

    LLM_INVOKE = "llm.invoke"
    TOOL_INVOKE = "tool.invoke"
    RETRIEVAL = "retrieval"
    EMBEDDING_GENERATE = "embedding.generate"
    AGENT_RUN = "agent.run"
    CHAIN_RUN = "chain.run"


# Base models
class SpanEvent(BaseModel):
    """OpenTelemetry span event."""

    name: str = Field(..., description="Event name (e.g., 'ai.prompt')")
    timestamp: datetime = Field(..., description="Event timestamp")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Event attributes")


class SpanLink(BaseModel):
    """OpenTelemetry span link."""

    trace_id: str = Field(..., description="Linked trace ID")
    span_id: str = Field(..., description="Linked span ID")
    attributes: Dict[str, Any] = Field(default_factory=dict)


class Resource(BaseModel):
    """OpenTelemetry resource attributes."""

    service_name: str = Field(..., alias="service.name")
    service_version: Optional[str] = Field(None, alias="service.version")
    deployment_environment: Optional[str] = Field(None, alias="deployment.environment")

    class Config:
        populate_by_name = True
        extra = "allow"  # Allow additional resource attributes


# AI-specific attribute models
class AILLMAttributes(BaseModel):
    """Attributes for LLM invocation spans."""

    operation_type: str = Field("llm.invoke", alias="ai.operation.type")
    model_provider: str = Field(
        ..., alias="ai.model.provider", description="e.g., 'openai', 'anthropic'"
    )
    model_name: str = Field(..., alias="ai.model.name", description="e.g., 'gpt-4'")
    request_type: str = Field("chat", alias="ai.llm.request.type")
    tokens_input: Optional[int] = Field(None, alias="ai.llm.tokens.input")
    tokens_output: Optional[int] = Field(None, alias="ai.llm.tokens.output")
    tokens_total: Optional[int] = Field(None, alias="ai.llm.tokens.total")
    finish_reason: Optional[str] = Field(None, alias="ai.llm.finish_reason")

    class Config:
        populate_by_name = True
        extra = "allow"


class AIToolAttributes(BaseModel):
    """Attributes for tool invocation spans."""

    operation_type: str = Field("tool.invoke", alias="ai.operation.type")
    tool_name: str = Field(..., alias="ai.tool.name")
    tool_type: str = Field(..., alias="ai.tool.type", description="e.g., 'http', 'function'")

    class Config:
        populate_by_name = True
        extra = "allow"


# Main span model
class OTELSpanCreate(BaseModel):
    """Schema for creating a span (from SDK)."""

    # OpenTelemetry identifiers
    trace_id: str = Field(..., description="Hex-encoded trace ID (32 chars)")
    span_id: str = Field(..., description="Hex-encoded span ID (16 chars)")
    parent_span_id: Optional[str] = Field(None, description="Hex-encoded parent span ID")

    # Rhesis identifiers (extracted from JWT or headers)
    project_id: str = Field(..., description="Rhesis project ID")
    environment: str = Field(
        "development",
        description="Environment (development, staging, production)",
    )

    # Span metadata
    span_name: str = Field(..., description="Span name (e.g., 'ai.llm.invoke')")
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
        """Validate trace ID format."""
        if len(v) != 32 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("trace_id must be 32-character hex string")
        return v.lower()

    @field_validator("span_id", "parent_span_id")
    @classmethod
    def validate_span_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate span ID format."""
        if v is None:
            return v
        if len(v) != 16 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("span_id must be 16-character hex string")
        return v.lower()

    @field_validator("end_time")
    @classmethod
    def validate_timing(cls, v: datetime, info) -> datetime:
        """Ensure end_time > start_time."""
        if "start_time" in info.data and v < info.data["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v


class OTELSpanResponse(BaseModel):
    """Schema for returning a span."""

    id: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    project_id: str
    organization_id: str
    environment: str
    span_name: str
    span_kind: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status_code: str
    status_message: Optional[str]
    attributes: Dict[str, Any]
    events: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    resource: Dict[str, Any]
    processed_at: Optional[datetime]
    enriched_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TraceResponse(BaseModel):
    """Response for trace ingestion."""

    status: str = Field("received", description="Status of trace ingestion")
    span_count: int = Field(..., description="Number of spans received")
    trace_id: str = Field(..., description="Trace ID")


# Batch ingestion
class OTELTraceBatch(BaseModel):
    """Batch of spans for ingestion."""

    spans: List[OTELSpanCreate] = Field(..., description="List of spans to ingest")

    @field_validator("spans")
    @classmethod
    def validate_batch_size(cls, v: List[OTELSpanCreate]) -> List[OTELSpanCreate]:
        """Limit batch size."""
        if len(v) > 1000:
            raise ValueError("Batch size cannot exceed 1000 spans")
        if len(v) == 0:
            raise ValueError("Batch cannot be empty")
        return v
