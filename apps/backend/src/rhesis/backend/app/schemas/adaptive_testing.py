"""Schemas for adaptive testing API (generate outputs, evaluate, etc.)."""

from typing import List, Optional

from pydantic import UUID4, BaseModel, Field

from rhesis.backend.app.schemas import Base

# ---------------------------------------------------------------------------
# Generate outputs
# ---------------------------------------------------------------------------


class GenerateOutputsRequest(Base):
    """Request body for generating test outputs via endpoint invocation."""

    endpoint_id: UUID4
    test_ids: Optional[List[UUID4]] = None
    topic: Optional[str] = None
    include_subtopics: bool = True


class GenerateOutputsUpdatedItem(BaseModel):
    """One test whose output was updated (stored in test_metadata)."""

    test_id: str
    output: str


class GenerateOutputsFailedItem(BaseModel):
    """One test that failed during output generation."""

    test_id: str
    error: str


class GenerateOutputsResponse(Base):
    """Response for generate outputs. Results are stored in test metadata."""

    generated: int
    failed: List[GenerateOutputsFailedItem]
    updated: List[GenerateOutputsUpdatedItem]


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------


class EvaluateRequest(Base):
    """Request body for evaluating adaptive tests with specified metrics."""

    metric_names: List[str] = Field(
        ...,
        min_length=1,
        description="Metric names to evaluate (must exist in the organization)",
    )
    test_ids: Optional[List[UUID4]] = None
    topic: Optional[str] = None
    include_subtopics: bool = True


class EvaluateResultItem(BaseModel):
    """One test that was evaluated successfully."""

    test_id: str
    label: str
    labeler: str
    model_score: float


class EvaluateFailedItem(BaseModel):
    """One test that failed during evaluation."""

    test_id: str
    error: str


class EvaluateResponse(Base):
    """Response for evaluate. Results are persisted in test metadata."""

    evaluated: int
    results: List[EvaluateResultItem]
    failed: List[EvaluateFailedItem]
