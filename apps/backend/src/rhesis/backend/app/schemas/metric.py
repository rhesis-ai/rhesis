from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

from pydantic import UUID4, ConfigDict

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.status import Status
from rhesis.backend.app.schemas.tag import Tag
from rhesis.backend.app.schemas.type_lookup import TypeLookup
from rhesis.backend.app.schemas.user import UserReference


class ScoreType(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


class ThresholdOperator(str, Enum):
    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN_OR_EQUAL = ">="
    NOT_EQUAL = "!="


class MetricScope(str, Enum):
    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"


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
    pass


class MetricUpdate(MetricBase):
    name: Optional[str] = None
    evaluation_prompt: Optional[str] = None
    score_type: Optional[ScoreType] = None
    threshold_operator: Optional[ThresholdOperator] = None


class Metric(MetricBase):
    id: UUID4
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]
    tags: Optional[List[Tag]] = []
    # Override string fields with relationship objects for response
    backend_type: Optional[TypeLookup] = None
    metric_type: Optional[TypeLookup] = None

    model_config = ConfigDict(from_attributes=True)


class MetricDetail(Metric):
    status: Optional[Status] = None
    assignee: Optional[UserReference] = None
    owner: Optional[UserReference] = None
