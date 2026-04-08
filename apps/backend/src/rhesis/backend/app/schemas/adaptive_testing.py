"""Schemas for adaptive testing API (generate outputs, evaluate, etc.)."""

from typing import Any, Dict, List, Optional

from pydantic import UUID4, BaseModel, Field

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.test_set import TestSet as TestSetSchema

# ---------------------------------------------------------------------------
# Import from existing test set
# ---------------------------------------------------------------------------


class ImportAdaptiveTestSetResponse(Base):
    """Response for POST /adaptive_testing/import/{source_test_set_id}."""

    test_set: TestSetSchema
    imported: int = 0
    skipped: int = 0
    skipped_test_ids: List[str] = Field(default_factory=list)


class ExportAdaptiveTestSetResponse(Base):
    """Response for POST /adaptive_testing/export/{source_test_set_id}."""

    test_set: TestSetSchema
    exported: int = 0
    skipped: int = 0
    skipped_test_ids: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Generate outputs
# ---------------------------------------------------------------------------


class GenerateOutputsRequest(Base):
    """Request body for generating test outputs via endpoint invocation."""

    endpoint_id: Optional[UUID4] = None
    test_ids: Optional[List[UUID4]] = None
    topic: Optional[str] = None
    include_subtopics: bool = True
    overwrite: bool = False


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
    skipped: int = 0
    failed: List[GenerateOutputsFailedItem]
    updated: List[GenerateOutputsUpdatedItem]


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------


class EvaluateRequest(Base):
    """Request body for evaluating adaptive tests with specified metrics."""

    metric_names: Optional[List[str]] = None
    test_ids: Optional[List[UUID4]] = None
    topic: Optional[str] = None
    include_subtopics: bool = True
    overwrite: bool = False


class AdaptiveMetricEvalDetail(BaseModel):
    """Per-metric evaluation row (keyed by metric name on the parent model)."""

    score: float
    is_successful: bool
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class EvaluateResultItem(BaseModel):
    """One test that was evaluated successfully."""

    test_id: str
    label: str
    labeler: str
    model_score: float
    metrics: Optional[Dict[str, AdaptiveMetricEvalDetail]] = None


class EvaluateFailedItem(BaseModel):
    """One test that failed during evaluation."""

    test_id: str
    error: str


class EvaluateResponse(Base):
    """Response for evaluate. Results are persisted in test metadata."""

    evaluated: int
    skipped: int = 0
    results: List[EvaluateResultItem]
    failed: List[EvaluateFailedItem]


# ---------------------------------------------------------------------------
# Generate suggestions
# ---------------------------------------------------------------------------


class GenerateSuggestionsRequest(Base):
    """Request body for generating test suggestions via LLM."""

    topic: Optional[str] = None
    num_examples: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of existing tests to sample as examples",
    )
    num_suggestions: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of new test suggestions to generate",
    )
    user_feedback: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional user guidance to steer suggestion generation",
    )


class SuggestedTest(BaseModel):
    """One LLM-generated test suggestion (not yet persisted)."""

    topic: str = ""
    input: str = ""
    output: str = ""
    label: str = ""
    labeler: str = ""
    model_score: float = 0.0


class GenerateSuggestionsResponse(Base):
    """Response containing LLM-generated test suggestions."""

    suggestions: List[SuggestedTest]
    num_examples_used: int


# ---------------------------------------------------------------------------
# Generate suggestion outputs (non-persisted)
# ---------------------------------------------------------------------------


class SuggestionInput(BaseModel):
    """A single suggestion input for output generation."""

    input: str
    topic: str = ""


class GenerateSuggestionOutputsRequest(Base):
    """Request body for generating outputs for non-persisted suggestions."""

    endpoint_id: Optional[UUID4] = None
    suggestions: List[SuggestionInput]


class SuggestionOutputItem(BaseModel):
    """Result of generating output for one suggestion."""

    input: str
    output: str = ""
    error: Optional[str] = None


class GenerateSuggestionOutputsResponse(Base):
    """Response for suggestion output generation (nothing persisted)."""

    generated: int
    results: List[SuggestionOutputItem]


# ---------------------------------------------------------------------------
# Evaluate suggestions (non-persisted)
# ---------------------------------------------------------------------------


class SuggestionForEval(BaseModel):
    """A single suggestion to evaluate."""

    input: str
    output: str


class EvaluateSuggestionsRequest(Base):
    """Request body for evaluating non-persisted suggestions."""

    metric_names: Optional[List[str]] = None
    suggestions: List[SuggestionForEval]


class SuggestionEvalItem(BaseModel):
    """Evaluation result for one suggestion."""

    input: str
    label: str = ""
    labeler: str = ""
    model_score: float = 0.0
    metrics: Optional[Dict[str, AdaptiveMetricEvalDetail]] = None
    error: Optional[str] = None


class EvaluateSuggestionsResponse(Base):
    """Response for suggestion evaluation (nothing persisted)."""

    evaluated: int
    results: List[SuggestionEvalItem]


# ---------------------------------------------------------------------------
# Adaptive testing settings
# ---------------------------------------------------------------------------


class AdaptiveSettingsUpdate(Base):
    """Request body for updating adaptive testing settings.

    Both fields are optional so callers can update only what changed.
    """

    default_endpoint_id: Optional[UUID4] = None
    metric_ids: Optional[List[UUID4]] = None


class AdaptiveSettingsMetric(BaseModel):
    """Lightweight metric reference returned inside settings."""

    id: UUID4
    name: str


class AdaptiveSettingsEndpoint(BaseModel):
    """Lightweight endpoint reference returned inside settings."""

    id: UUID4
    name: str


class AdaptiveSettingsResponse(Base):
    """Response for GET/PUT adaptive testing settings."""

    default_endpoint: Optional[AdaptiveSettingsEndpoint] = None
    metrics: List[AdaptiveSettingsMetric] = []
