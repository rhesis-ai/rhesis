from typing import Any, Dict, Optional

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
    test_reviews = Column(JSONB)
    user_id = Column(GUID(), ForeignKey("user.id"))
    organization_id = Column(GUID(), ForeignKey("organization.id"))
    test_configuration = relationship("TestConfiguration", back_populates="test_results")
    test_run = relationship("TestRun", back_populates="test_results")
    user = relationship("User", back_populates="test_results")
    status = relationship("Status", back_populates="test_results")
    organization = relationship("Organization", back_populates="test_results")
    test = relationship("Test", back_populates="test_results")

    @property
    def last_review(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent review from test_reviews based on updated_at timestamp.

        Returns:
            The most recent review object, or None if no reviews exist.
        """
        if not self.test_reviews or not isinstance(self.test_reviews, dict):
            return None

        reviews = self.test_reviews.get("reviews", [])
        if not reviews or not isinstance(reviews, list):
            return None

        # Sort reviews by updated_at timestamp (most recent first)
        # Handle cases where updated_at might not exist by falling back to created_at
        sorted_reviews = sorted(
            reviews,
            key=lambda r: r.get("updated_at") or r.get("created_at") or "",
            reverse=True,
        )

        return sorted_reviews[0] if sorted_reviews else None

    @property
    def matches_review(self) -> bool:
        """
        Check if the test result's status_id matches the status_id from the latest review.

        Returns:
            True if the test result status matches the latest review status, False otherwise.
            Returns False if there are no reviews or if either status is missing.
        """
        last_review = self.last_review
        if not last_review:
            return False

        # Get the status from the review
        review_status = last_review.get("status")
        if not review_status or not isinstance(review_status, dict):
            return False

        review_status_id = review_status.get("status_id")
        if not review_status_id or not self.status_id:
            return False

        # Convert both to strings for comparison (they might be UUID objects or strings)
        return str(self.status_id) == str(review_status_id)
