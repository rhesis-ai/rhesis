from sqlalchemy import (
    Column,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.constants import (
    LEGACY_TARGET_TEST,
    REVIEW_TARGET_TEST_RESULT,
)

from .base import Base
from .guid import GUID
from .mixins import (
    CommentsMixin,
    CountsMixin,
    EmbeddableMixin,
    FilesMixin,
    ReviewsMixin,
    TagsMixin,
    TasksMixin,
)


class TestResult(
    Base,
    EmbeddableMixin,
    TagsMixin,
    CommentsMixin,
    TasksMixin,
    CountsMixin,
    FilesMixin,
    ReviewsMixin,
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

    def to_searchable_text(self) -> str:
        """
        Generate searchable text from test result fields for embeddings and full-text search.
        Extracts relevant information from test_output, status, and evaluator reasoning.
        """
        content = []

        if self.status:
            content.append(self.status.name)

        if self.test_output:
            if isinstance(self.test_output, dict):
                # Extract common output fields
                output_text = self.test_output.get("response") or self.test_output.get("output")
                if output_text:
                    content.append(str(output_text))
                else:
                    # Fallback: stringify all values if known keys are missing
                    content.append(" ".join(str(v) for v in self.test_output.values() if v))
            else:
                content.append(str(self.test_output))

        if self.test_metrics and isinstance(self.test_metrics, dict):
            # Extract evaluator reasoning from metrics (e.g. LLM judge explaining why it failed)
            for metric_data in self.test_metrics.values():
                if isinstance(metric_data, dict):
                    reason = metric_data.get("reason") or metric_data.get("reasoning")
                    if reason:
                        content.append(str(reason))

        return " ".join(filter(None, content)).strip()
