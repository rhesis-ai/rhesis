from sqlalchemy import (
    Column,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin


class ResponsePattern(Base, OrganizationAndUserMixin):
    __tablename__ = "response_pattern"
    text = Column(Text, nullable=False)
    response_pattern_type_id = Column(GUID(), ForeignKey("type_lookup.id"))
    behavior_id = Column(GUID(), ForeignKey("behavior.id"))
    # Relationship back to the behavior
    behavior = relationship("Behavior", back_populates="response_patterns")
    response_pattern_type = relationship("TypeLookup", back_populates="response_patterns")
