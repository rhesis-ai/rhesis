from sqlalchemy import (
    Column,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import OrganizationAndUserMixin


class TypeLookup(Base, OrganizationAndUserMixin):
    __tablename__ = "type_lookup"
    type_name = Column(String)  # 'CategoryType', 'ResponsePatternType', 'EntityType', etc.
    type_value = Column(String)  # 'TYPE_A', 'TYPE_B', etc.
    description = Column(Text)

    statuses = relationship("Status", back_populates="entity_type")
    categories = relationship("Category", back_populates="entity_type")
    response_patterns = relationship("ResponsePattern", back_populates="response_pattern_type")
    topics = relationship("Topic", back_populates="entity_type")
    test_sets = relationship("TestSet", back_populates="license_type")
    tests = relationship("Test", back_populates="test_type")
    metrics = relationship("Metric", foreign_keys="[Metric.metric_type_id]", back_populates="metric_type")
    models = relationship("Model", back_populates="provider_type")
    backend_types = relationship("Metric", foreign_keys="[Metric.backend_type_id]", back_populates="backend_type")