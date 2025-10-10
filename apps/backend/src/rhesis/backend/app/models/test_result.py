from sqlalchemy import (
    Column,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import CommentsMixin, CountsMixin, TagsMixin, TasksMixin


class TestResult(Base, TagsMixin, CommentsMixin, TasksMixin, CountsMixin):
    __tablename__ = "test_result"
    test_configuration_id = Column(GUID(), ForeignKey("test_configuration.id"))
    test_run_id = Column(GUID(), ForeignKey("test_run.id"))
    prompt_id = Column(GUID(), ForeignKey("prompt.id"))
    test_id = Column(GUID(), ForeignKey("test.id"))
    status_id = Column(GUID(), ForeignKey("status.id"))
    test_output = Column(JSONB)
    test_metrics = Column(JSONB)
    user_id = Column(GUID(), ForeignKey("user.id"))
    organization_id = Column(GUID(), ForeignKey("organization.id"))
    test_configuration = relationship("TestConfiguration", back_populates="test_results")
    test_run = relationship("TestRun", back_populates="test_results")
    user = relationship("User", back_populates="test_results")
    status = relationship("Status", back_populates="test_results")
    organization = relationship("Organization", back_populates="test_results")
    test = relationship("Test", back_populates="test_results")
