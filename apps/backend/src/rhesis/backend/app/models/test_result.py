from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.schemas.test_result import VALID_TARGET_TYPES

from .base import Base
from .guid import GUID
from .mixins import CommentsMixin, CountsMixin, FilesMixin, TagsMixin, TasksMixin

_LEGACY_TEST_TYPE = "test"
_TEST_RESULT_TYPE = VALID_TARGET_TYPES[0]  # "test_result"
_TEST_RESULT_TYPES = (_TEST_RESULT_TYPE, _LEGACY_TEST_TYPE)


class TestResult(Base, TagsMixin, CommentsMixin, TasksMixin, CountsMixin, FilesMixin):
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

    def _get_all_reviews(self) -> List[Dict[str, Any]]:
        if not self.test_reviews or not isinstance(self.test_reviews, dict):
            return []
        reviews = self.test_reviews.get("reviews", [])
        if not reviews or not isinstance(reviews, list):
            return []
        return reviews

    @staticmethod
    def _get_target_type(review: Dict[str, Any]) -> str:
        target = review.get("target") or {}
        return target.get("type", _TEST_RESULT_TYPE)

    @property
    def last_review(self) -> Optional[Dict[str, Any]]:
        """Most recent test_result-level review (for overall status comparison)."""
        reviews = self._get_all_reviews()
        test_result_reviews = [r for r in reviews if self._get_target_type(r) in _TEST_RESULT_TYPES]
        if not test_result_reviews:
            return None

        sorted_reviews = sorted(
            test_result_reviews,
            key=lambda r: r.get("updated_at") or r.get("created_at") or "",
            reverse=True,
        )
        return sorted_reviews[0]

    @property
    def matches_review(self) -> bool:
        """Check if the test result status matches the latest test_result-level review."""
        last_review = self.last_review
        if not last_review:
            return False

        review_status = last_review.get("status")
        if not review_status or not isinstance(review_status, dict):
            return False

        review_status_id = review_status.get("status_id")
        if not review_status_id or not self.status_id:
            return False

        return str(self.status_id) == str(review_status_id)

    @property
    def review_summary(self) -> Optional[Dict[str, Any]]:
        """Per-target-type summary of reviews for frontend consumption."""
        reviews = self._get_all_reviews()
        if not reviews:
            return None

        summary: Dict[str, Any] = {}
        for review in reviews:
            target_type = self._get_target_type(review)
            if target_type == _LEGACY_TEST_TYPE:
                target_type = _TEST_RESULT_TYPE
            target = review.get("target") or {}
            reference = target.get("reference")
            key = f"{target_type}:{reference}" if reference else target_type

            ts = review.get("updated_at") or review.get("created_at") or ""
            existing = summary.get(key)
            if not existing or ts > (
                existing.get("updated_at") or existing.get("created_at") or ""
            ):
                summary[key] = {
                    "target_type": target_type,
                    "reference": reference,
                    "status": review.get("status"),
                    "user": review.get("user"),
                    "updated_at": ts,
                    "review_id": review.get("review_id"),
                }

        return summary
