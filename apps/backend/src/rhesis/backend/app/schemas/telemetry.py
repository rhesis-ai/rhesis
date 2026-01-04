"""Backend telemetry schemas - imports from SDK."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# Import canonical schemas from SDK (source of truth)
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

from .comment import Comment
from .tag import TagRead

# Re-export SDK schemas for backward compatibility
__all__ = [
    "SpanKind",
    "StatusCode",
    "AIOperationType",
    "SpanEvent",
    "SpanLink",
    "AILLMAttributes",
    "AIToolAttributes",
    "OTELSpan",
    "OTELTraceBatch",
    "TraceIngestResponse",
    "OTELSpanResponse",
    "OTELSpanDB",
    "TraceSummary",
    "TraceListResponse",
    "SpanNode",
    "TraceDetailResponse",
    "TraceMetricsResponse",
]

# Alias for consistency with existing backend code
OTELSpanCreate = OTELSpan


# Backend-specific models (not in SDK)
class OTELSpanResponse(BaseModel):
    """Schema for returning a span from the database."""

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

    # Tags and comments
    tags: Optional[List[TagRead]] = Field(
        default_factory=list, description="Tags associated with this trace"
    )
    comments: Optional[List[Comment]] = Field(
        default_factory=list, description="Comments associated with this trace"
    )

    model_config = ConfigDict(from_attributes=True)


class OTELSpanDB(BaseModel):
    """Database model with persistence fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    processed_at: Optional[datetime] = None
    enriched_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    span_data: OTELSpan


# Legacy alias (deprecated - use TraceIngestResponse)
TraceResponse = TraceIngestResponse


# Query response schemas
class TraceSummary(BaseModel):
    """Summary of a trace for list view."""

    trace_id: str
    project_id: str
    environment: str
    start_time: datetime
    duration_ms: float
    span_count: int
    root_operation: str
    status_code: str
    total_tokens: Optional[int] = None
    total_cost_usd: Optional[float] = None
    total_cost_eur: Optional[float] = None
    has_errors: bool

    # Test execution context (optional - only present for test execution traces)
    test_run_id: Optional[str] = Field(
        default=None, description="Test run ID if this trace is from a test execution"
    )
    test_result_id: Optional[str] = Field(
        default=None, description="Test result ID if this trace is from a test execution"
    )
    test_id: Optional[str] = Field(
        default=None, description="Test ID if this trace is from a test execution"
    )

    # Tags and comments count for summary view
    tags_count: Optional[int] = Field(
        default=0, description="Number of tags associated with this trace"
    )
    comments_count: Optional[int] = Field(
        default=0, description="Number of comments associated with this trace"
    )

    model_config = ConfigDict(from_attributes=True)


class TraceListResponse(BaseModel):
    """Response for list traces endpoint."""

    traces: List[TraceSummary]
    total: int = Field(..., description="Total traces matching filters")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Pagination offset")


class SpanNode(BaseModel):
    """Span node in trace tree."""

    span_id: str
    span_name: str
    span_kind: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status_code: str
    status_message: Optional[str]
    attributes: Dict[str, Any]
    events: List[Dict[str, Any]]
    children: List["SpanNode"] = Field(default_factory=list)

    # Tags and comments
    tags: Optional[List[TagRead]] = Field(
        default_factory=list, description="Tags associated with this span"
    )
    comments: Optional[List[Comment]] = Field(
        default_factory=list, description="Comments associated with this span"
    )


class TraceDetailResponse(BaseModel):
    """Detailed trace with full span tree."""

    trace_id: str
    project_id: str
    environment: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    span_count: int
    error_count: int
    total_tokens: int
    total_cost_usd: float
    root_spans: List[SpanNode]


class TraceMetricsResponse(BaseModel):
    """Aggregated metrics for traces."""

    total_traces: int
    total_spans: int
    total_tokens: int
    total_cost_usd: float
    error_rate: float
    avg_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    operation_breakdown: Dict[str, int]  # operation_type -> count
