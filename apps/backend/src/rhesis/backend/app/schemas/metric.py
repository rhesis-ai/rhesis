from datetime import datetime
from typing import List, Optional, Union
from enum import Enum

from pydantic import UUID4, Field

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.user import UserReference
from rhesis.backend.app.schemas.status import Status
from rhesis.backend.app.schemas.type_lookup import TypeLookup
from rhesis.backend.app.schemas.tag import Tag

class ScoreType(str, Enum):
    BINARY = "binary"
    NUMERIC = "numeric"


class ThresholdOperator(str, Enum):
    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN_OR_EQUAL = ">="
    NOT_EQUAL = "!="


class MetricBase(Base):
    name: str
    description: Optional[str] = None
    evaluation_prompt: str
    evaluation_steps: Optional[str] = None
    reasoning: Optional[str] = None
    score_type: ScoreType
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    threshold: Optional[float] = None
    threshold_operator: Optional[ThresholdOperator] = ThresholdOperator.GREATER_THAN_OR_EQUAL
    explanation: Optional[str] = None
    metric_type_id: Optional[UUID4] = None
    backend_type_id: Optional[UUID4] = None
    model_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    class_name: Optional[str] = None
    context_required: Optional[bool] = False
    evaluation_examples: Optional[str] = None

class MetricCreate(MetricBase):
    pass


class MetricUpdate(MetricBase):
    title: Optional[str] = None
    evaluation_prompt: Optional[str] = None
    score_type: Optional[ScoreType] = None
    threshold_operator: Optional[ThresholdOperator] = None


class Metric(MetricBase):
    id: UUID4
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]
    tags: Optional[List[Tag]] = []

    class Config:
        from_attributes = True


class MetricDetail(Metric):
    metric_type: Optional[TypeLookup] = None
    status: Optional[Status] = None
    assignee: Optional[UserReference] = None
    owner: Optional[UserReference] = None 