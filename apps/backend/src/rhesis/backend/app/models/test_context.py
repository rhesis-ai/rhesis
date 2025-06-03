from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin


class TestContext(Base, OrganizationAndUserMixin):
    __tablename__ = "test_context"

    test_id = Column(GUID(), ForeignKey("test.id"), nullable=False)
    entity_id = Column(GUID(), nullable=False)  # The ID of the related entity
    entity_type = Column(String, nullable=False)  # The type of the related entity
    attributes = Column(JSONB)  # Additional context specifications

    # Relationship back to the Test
    test = relationship("Test", back_populates="test_contexts")

    # Polymorphic association
    __mapper_args__ = {"polymorphic_on": entity_type, "polymorphic_identity": "test_context"}
