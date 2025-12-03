from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import (
    ActivityTrackableMixin,
    CommentsMixin,
    CountsMixin,
    OrganizationAndUserMixin,
    TasksMixin,
)


class Behavior(
    Base, ActivityTrackableMixin, OrganizationAndUserMixin, CommentsMixin, TasksMixin, CountsMixin
):
    __tablename__ = "behavior"
    name = Column(String, nullable=False)
    description = Column(Text)
    status_id = Column(GUID(), ForeignKey("status.id"))

    response_patterns = relationship("ResponsePattern", back_populates="behavior")
    status = relationship("Status", back_populates="behaviors")
    prompts = relationship("Prompt", back_populates="behavior")
    tests = relationship("Test", back_populates="behavior")
    metrics = relationship("Metric", secondary="behavior_metric", back_populates="behaviors")
