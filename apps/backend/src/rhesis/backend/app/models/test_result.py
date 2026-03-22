from typing import Any, Dict, List, Optional

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
from .mixins import CommentsMixin, CountsMixin, FilesMixin, TagsMixin, TasksMixin

_TEST_RESULT_TYPE = REVIEW_TARGET_TEST_RESULT
_TEST_RESULT_TYPES = (REVIEW_TARGET_TEST_RESULT, LEGACY_TARGET_TEST)


class TestResult(Base, TagsMixin, CommentsMixin, TasksMixin, CountsMixin, FilesMixin):
    __tablename__ = "test_result"
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

    def _compute_review_state(
        self,
    ) -> tuple:
        """
        Single-pass over all reviews. Returns (last_review, matches_review, review_summary).

        Consolidates the three derived properties so callers can obtain all
        values without repeated iteration.
        """
        reviews = self._get_all_reviews()
        if not reviews:
            return None, False, None

        summary: Dict[str, Any] = {}
        test_result_level: List[Dict[str, Any]] = []

        for review in reviews:
            raw_type = self._get_target_type(review)
            canonical_type = _TEST_RESULT_TYPE if raw_type == LEGACY_TARGET_TEST else raw_type

            # Accumulate per-target summary (latest review wins per key)
            target = review.get("target") or {}
            reference = target.get("reference")
            key = f"{canonical_type}:{reference}" if reference else canonical_type
            ts = review.get("updated_at") or review.get("created_at") or ""
            existing = summary.get(key)
            _ex = existing or {}
            existing_ts = _ex.get("updated_at") or _ex.get("created_at") or ""
            if not existing or ts > existing_ts:
                summary[key] = {
                    "target_type": canonical_type,
                    "reference": reference,
                    "status": review.get("status"),
                    "user": review.get("user"),
                    "updated_at": ts,
                    "review_id": review.get("review_id"),
                }

            # Collect test_result-level reviews for last_review calculation
            if raw_type in _TEST_RESULT_TYPES:
                test_result_level.append(review)

        # Determine last_review
        last_review: Optional[Dict[str, Any]] = None
        if test_result_level:
            last_review = max(
                test_result_level,
                key=lambda r: r.get("updated_at") or r.get("created_at") or "",
            )

        # Determine matches_review
        matches = False
        if last_review:
            review_status = last_review.get("status")
            if review_status and isinstance(review_status, dict):
                review_status_id = review_status.get("status_id")
                if review_status_id and self.status_id:
                    matches = str(self.status_id) == str(review_status_id)

        return last_review, matches, summary if summary else None

    @property
    def last_review(self) -> Optional[Dict[str, Any]]:
        """Most recent test_result-level review (for overall status comparison)."""
        return self._compute_review_state()[0]

    @property
    def matches_review(self) -> bool:
        """Check if the test result status matches the latest test_result-level review."""
        return self._compute_review_state()[1]

    @property
    def review_summary(self) -> Optional[Dict[str, Any]]:
        """Per-target-type summary of reviews for frontend consumption."""
        return self._compute_review_state()[2]
