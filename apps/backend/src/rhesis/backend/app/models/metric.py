from enum import Enum

from sqlalchemy import Boolean, Column, Float, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import (
    ActivityTrackableMixin,
    CommentsMixin,
    CountsMixin,
    OrganizationMixin,
    TagsMixin,
    TasksMixin,
    UserOwnedMixin,
)

# Association table for behavior and metric
behavior_metric_association = Table(
    "behavior_metric",
    Base.metadata,
    Column("behavior_id", GUID(), ForeignKey("behavior.id"), primary_key=True),
    Column("metric_id", GUID(), ForeignKey("metric.id"), primary_key=True),
    Column("user_id", GUID(), ForeignKey("user.id"), nullable=False),
    Column("organization_id", GUID(), ForeignKey("organization.id"), nullable=False),
)


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


class Metric(
    Base,
    ActivityTrackableMixin,
    TagsMixin,
    UserOwnedMixin,
    OrganizationMixin,
    CommentsMixin,
    TasksMixin,
    CountsMixin,
):
    __tablename__ = "metric"

    name = Column(String, nullable=False)
    description = Column(Text)
    evaluation_prompt = Column(Text, nullable=False)
    evaluation_steps = Column(Text)
    reasoning = Column(Text)
    score_type = Column(String, nullable=False)
    min_score = Column(Float)
    max_score = Column(Float)
    reference_score = Column(String)  # @deprecated: kept for transition, use categories instead
    categories = Column(JSONB)  # List of valid categories for categorical metrics
    passing_categories = Column(JSONB)  # List of categories that indicate pass
    threshold = Column(Float)
    threshold_operator = Column(String, default=ThresholdOperator.GREATER_THAN_OR_EQUAL.value)
    explanation = Column(Text)
    ground_truth_required = Column(Boolean, default=False)
    context_required = Column(Boolean, default=False)
    class_name = Column(String)  # useful if type is custom code or framework
    evaluation_examples = Column(String)
    metric_scope = Column(
        JSONB
    )  # Array of test types this metric applies to (Single-Turn, Multi-Turn)

    # Foreign keys
    metric_type_id = Column(GUID(), ForeignKey("type_lookup.id"))
    status_id = Column(GUID(), ForeignKey("status.id"))
    assignee_id = Column(GUID(), ForeignKey("user.id"))
    owner_id = Column(GUID(), ForeignKey("user.id"))
    model_id = Column(GUID(), ForeignKey("model.id"), nullable=True)
    backend_type_id = Column(GUID(), ForeignKey("type_lookup.id"))

    # Relationships
    metric_type = relationship(
        "TypeLookup", foreign_keys=[metric_type_id], back_populates="metrics"
    )
    status = relationship("Status", back_populates="metrics")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_metrics")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_metrics")
    model = relationship("Model", back_populates="metrics")
    backend_type = relationship(
        "TypeLookup", foreign_keys=[backend_type_id], back_populates="backend_types"
    )
    behaviors = relationship(
        "Behavior", secondary=behavior_metric_association, back_populates="metrics"
    )
