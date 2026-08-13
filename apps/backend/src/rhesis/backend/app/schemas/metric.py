from enum import Enum
from typing import List, Optional

from pydantic import UUID4, ConfigDict, Field, field_validator, model_validator

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.metric_types import ScoreType, ThresholdOperator
from rhesis.backend.app.schemas.references import RequirementReference
from rhesis.backend.app.schemas.tag import Tag
from rhesis.backend.app.schemas.type_lookup import TypeLookup


class MetricScope(str, Enum):
    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"
    TRACE = "Trace"


class MetricBase(Base):
    name: str
    description: Optional[str] = None
    evaluation_prompt: str
    evaluation_steps: Optional[str] = None
    reasoning: Optional[str] = None
    score_type: ScoreType
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    reference_score: Optional[str] = (
        None  # @deprecated: kept for transition, use categories instead
    )
    categories: Optional[List[str]] = None  # List of valid categories for categorical metrics
    passing_categories: Optional[List[str]] = None  # Categories that indicate pass
    threshold: Optional[float] = None
    threshold_operator: Optional[ThresholdOperator] = ThresholdOperator.GREATER_THAN_OR_EQUAL
    explanation: Optional[str] = None
    # ID fields (used internally)
    metric_type_id: Optional[UUID4] = None
    backend_type_id: Optional[UUID4] = None
    model_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    # String fields (from SDK, will be converted to IDs)
    metric_type: Optional[str] = None
    backend_type: Optional[str] = None
    class_name: Optional[str] = None
    ground_truth_required: Optional[bool] = False
    context_required: Optional[bool] = False
    evaluation_examples: Optional[str] = None
    metric_scope: Optional[List[MetricScope]] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


class MetricCreate(MetricBase):
    # Required on create, unlike the rest of MetricBase. A metric with no scope is
    # filtered out by every execution path, so accepting one silently creates dead
    # configuration that never evaluates and reports no error. Enforced here rather
    # than only in the UI so the SDK, MCP, and the Architect agent are covered too;
    # the metric table also carries a CHECK constraint as a backstop.
    metric_scope: List[MetricScope] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_score_type_fields(self) -> "MetricCreate":
        if self.score_type == ScoreType.NUMERIC:
            if self.min_score is None:
                raise ValueError("min_score is required for numeric metrics")
            if self.max_score is None:
                raise ValueError("max_score is required for numeric metrics")
            if self.threshold is None:
                raise ValueError("threshold is required for numeric metrics")
        elif self.score_type == ScoreType.CATEGORICAL:
            if not self.categories or len(self.categories) < 2:
                raise ValueError("at least 2 categories are required for categorical metrics")
            if not self.passing_categories or len(self.passing_categories) < 1:
                raise ValueError("at least 1 passing category is required for categorical metrics")
        return self


class MetricUpdate(MetricBase):
    name: Optional[str] = None
    evaluation_prompt: Optional[str] = None
    score_type: Optional[ScoreType] = None
    threshold_operator: Optional[ThresholdOperator] = None

    @field_validator("metric_scope")
    @classmethod
    def scope_cannot_be_emptied(cls, v: Optional[List[MetricScope]]) -> Optional[List[MetricScope]]:
        """None means "not being updated"; an empty list would disable the metric."""
        if v is not None and len(v) == 0:
            raise ValueError("metric_scope cannot be empty")
        return v


class Metric(MetricBase):
    id: UUID4
    tags: Optional[List[Tag]] = []
    # Override string fields with relationship objects for response
    backend_type: Optional[TypeLookup] = None
    metric_type: Optional[TypeLookup] = None

    model_config = ConfigDict(from_attributes=True)


class ModelReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MetricDetail(Metric):
    name: Optional[str] = None
    model: Optional[ModelReference] = None
    requirements: Optional[List[RequirementReference]] = []


class GenerateMetricRequest(Base):
    """Request body for POST /metrics/generate.

    The LLM uses the prompt to produce all required metric fields.
    """

    prompt: str


class ImproveMetricRequest(Base):
    """Request body for POST /metrics/{metric_id}/improve.

    The LLM uses the prompt to update the existing metric fields.
    """

    prompt: str
