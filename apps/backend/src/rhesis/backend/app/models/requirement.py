from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import (
    ActivityTrackableMixin,
    CommentsMixin,
    CountsMixin,
    OrganizationAndUserMixin,
    ProjectMixin,
    TagsMixin,
    TasksMixin,
)


class Requirement(
    Base,
    ActivityTrackableMixin,
    ProjectMixin,
    OrganizationAndUserMixin,
    TagsMixin,
    CommentsMixin,
    TasksMixin,
    CountsMixin,
):
    __tablename__ = "requirement"
    name = Column(String, nullable=False)
    description = Column(Text)
    status_id = Column(GUID(), ForeignKey("status.id"))

    status = relationship("Status", back_populates="requirements")
    prompts = relationship("Prompt", back_populates="requirement")
    tests = relationship("Test", back_populates="requirement")
    metrics = relationship("Metric", secondary="requirement_metric", back_populates="requirements")
