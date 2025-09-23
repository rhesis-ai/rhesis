from enum import Enum

from sqlalchemy import Boolean, Column, Float, ForeignKey, String, Table, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationMixin, TagsMixin, UserOwnedMixin

# Association table for behavior and metric
behavior_metric_association = Table(
    "behavior_metric",
    Base.metadata,
    Column("behavior_id", GUID(), ForeignKey("behavior.id"), primary_key=True),
    Column("metric_id", GUID(), ForeignKey("metric.id"), primary_key=True),
    Column("user_id", GUID(), ForeignKey("user.id")),
    Column("organization_id", GUID(), ForeignKey("organization.id")),
)


class ScoreType(str, Enum):
    BINARY = "binary"
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"


class ThresholdOperator(str, Enum):
    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN_OR_EQUAL = ">="
    NOT_EQUAL = "!="


class Metric(Base, TagsMixin, UserOwnedMixin, OrganizationMixin):
    __tablename__ = "metric"

    name = Column(String, nullable=False)
    description = Column(Text)
    evaluation_prompt = Column(Text, nullable=False)
    evaluation_steps = Column(Text)
    reasoning = Column(Text)
    score_type = Column(String, nullable=False)
    min_score = Column(Float)
    max_score = Column(Float)
    reference_score = Column(String)  # used for binary or categorical metrics
    threshold = Column(Float)
    threshold_operator = Column(String, default=ThresholdOperator.GREATER_THAN_OR_EQUAL.value)
    explanation = Column(Text)
    ground_truth_required = Column(Boolean, default=False)
    context_required = Column(Boolean, default=False)
    class_name = Column(String)  # useful if type is custom code or framework
    evaluation_examples = Column(String)

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
    # Comment relationship (polymorphic)
    comments = relationship(
        "Comment",
        primaryjoin="and_(Comment.entity_id == foreign(Metric.id), Comment.entity_type == 'Metric')",
        viewonly=True,
        uselist=True,
    )
    # Task relationship (polymorphic)
    tasks = relationship(
        "Task",
        primaryjoin="and_(Task.entity_id == foreign(Metric.id), Task.entity_type == 'Metric')",
        viewonly=True,
        uselist=True,
    )

    @property
    def comment_count(self):
        """Get the count of comments for this metric"""
        return len(self.comments) if self.comments else 0

    @property
    def task_count(self):
        """Get the count of tasks for this metric"""
        return len(self.tasks) if self.tasks else 0
