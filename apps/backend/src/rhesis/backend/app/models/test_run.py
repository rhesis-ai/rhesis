from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.models.guid import GUID

from .base import Base
from .mixins import (
    ActivityTrackableMixin,
    CommentsMixin,
    CountsMixin,
    OrganizationMixin,
    TagsMixin,
    TasksMixin,
)


class TestRun(
    Base,
    ActivityTrackableMixin,
    TagsMixin,
    OrganizationMixin,
    CommentsMixin,
    TasksMixin,
    CountsMixin,
):
    __tablename__ = "test_run"

    user_id = Column(GUID(), ForeignKey("user.id"))
    status_id = Column(GUID(), ForeignKey("status.id"))
    test_configuration_id = Column(GUID(), ForeignKey("test_configuration.id"), nullable=False)
    name = Column(String)
    attributes = Column(JSONB)
    owner_id = Column(GUID(), ForeignKey("user.id"))
    assignee_id = Column(GUID(), ForeignKey("user.id"))

    # Relationship to status
    status = relationship("Status", back_populates="test_runs")

    # Relationship to user
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_test_runs")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_test_runs")

    # Relationship to user
    user = relationship("User", foreign_keys=[user_id], back_populates="test_runs")
    test_configuration = relationship("TestConfiguration", back_populates="test_runs")
    test_results = relationship("TestResult", back_populates="test_run")
    organization = relationship("Organization", back_populates="test_runs")

    # Comment relationship (polymorphic)
    comments = relationship(
        "Comment",
        primaryjoin="and_(Comment.entity_id == foreign(TestRun.id), Comment.entity_type == 'TestRun')",
        viewonly=True,
        uselist=True,
    )
