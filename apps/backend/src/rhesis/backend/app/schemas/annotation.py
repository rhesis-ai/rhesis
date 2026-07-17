"""Schemas for the cross-entity annotations list (flattened reviews)."""

from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import Field

from rhesis.backend.app.schemas import Base


class AnnotationListItem(Base):
    """One human review flattened from test_result or trace JSONB."""

    review_id: str
    source: Literal["test_result", "trace"]
    comments: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    status: Dict[str, Any] = Field(default_factory=dict)
    user: Dict[str, Any] = Field(default_factory=dict)
    target: Dict[str, Any] = Field(default_factory=dict)
    resolved: bool = False

    # Deep-link fields
    test_result_id: Optional[UUID] = None
    test_run_id: Optional[UUID] = None
    trace_db_id: Optional[UUID] = None
    trace_id: Optional[str] = None
    project_id: Optional[UUID] = None
    span_name: Optional[str] = None
    # From the linked test (test results only; null for traces)
    behavior_id: Optional[UUID] = None
    behavior_name: Optional[str] = None


class AnnotationListResponse(Base):
    """Paginated annotations list with total count (also in X-Total-Count)."""

    items: list[AnnotationListItem]
    total_count: int
