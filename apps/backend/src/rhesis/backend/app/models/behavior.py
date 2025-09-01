from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin


class Behavior(Base, OrganizationAndUserMixin):
    __tablename__ = "behavior"
    name = Column(String, nullable=False)
    description = Column(Text)
    status_id = Column(GUID(), ForeignKey("status.id"))

    response_patterns = relationship("ResponsePattern", back_populates="behavior")
    status = relationship("Status", back_populates="behaviors")
    prompts = relationship("Prompt", back_populates="behavior")
    tests = relationship("Test", back_populates="behavior")
    metrics = relationship("Metric", secondary="behavior_metric", back_populates="behaviors")

    # Comment relationship (polymorphic)
    comments = relationship(
        "Comment",
        primaryjoin="and_(Comment.entity_id == foreign(Behavior.id), Comment.entity_type == 'Behavior')",
        viewonly=True,
    )
