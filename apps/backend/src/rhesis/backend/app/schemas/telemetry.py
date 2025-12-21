"""Backend telemetry schemas - imports from SDK."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

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

    class Config:
        from_attributes = True


class OTELSpanDB(BaseModel):
    """Database model with persistence fields."""

    id: str
    organization_id: str
    processed_at: Optional[datetime] = None
    enriched_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    span_data: OTELSpan

    class Config:
        from_attributes = True


# Legacy alias (deprecated - use TraceIngestResponse)
TraceResponse = TraceIngestResponse
