from sqlalchemy import (
    Column,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.schemas.test_result import (
    LEGACY_TARGET_TEST,
    REVIEW_TARGET_TEST_RESULT,
)

from .base import Base
from .guid import GUID
from .mixins import (
    CommentsMixin,
    CountsMixin,
    FilesMixin,
    ReviewsMixin,
    TagsMixin,
    TasksMixin,
)


class TestResult(
    Base, TagsMixin, CommentsMixin, TasksMixin, CountsMixin, FilesMixin, ReviewsMixin
):
    __tablename__ = "test_result"

    _reviews_column_name = "test_reviews"
    _reviews_entity_type = REVIEW_TARGET_TEST_RESULT
    _reviews_legacy_types = (LEGACY_TARGET_TEST,)

    test_configuration_id = Column(GUID(), ForeignKey("test_configuration.id"))
    test_run_id = Column(GUID(), ForeignKey("test_run.id"), index=True)
    prompt_id = Column(GUID(), ForeignKey("prompt.id"))
    test_id = Column(GUID(), ForeignKey("test.id"), index=True)
    status_id = Column(GUID(), ForeignKey("status.id"), index=True)
    test_output = Column(JSONB)
    test_metrics = Column(JSONB)
    test_reviews = Column(JSONB)
    user_id = Column(GUID(), ForeignKey("user.id"))
    organization_id = Column(GUID(), ForeignKey("organization.id"), index=True)
    test_configuration = relationship("TestConfiguration", back_populates="test_results")
    test_run = relationship("TestRun", back_populates="test_results")
    user = relationship("User", back_populates="test_results")
    status = relationship("Status", back_populates="test_results")
    organization = relationship("Organization", back_populates="test_results")
    test = relationship("Test", back_populates="test_results")
