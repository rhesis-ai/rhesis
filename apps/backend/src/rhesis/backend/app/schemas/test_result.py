from typing import Any, Dict, Optional, Union

from pydantic import UUID4, ConfigDict, Field, field_validator

from rhesis.backend.app.constants import (
    LEGACY_TARGET_TEST,
    REVIEW_TARGET_TEST_RESULT,
    ReviewTarget,
)
from rhesis.backend.app.schemas import Base

# Re-export for backward compatibility
REVIEW_TARGET_TRACE = ReviewTarget.TRACE
REVIEW_TARGET_TURN = ReviewTarget.TURN
REVIEW_TARGET_METRIC = ReviewTarget.METRIC
VALID_TARGET_TYPES = tuple(ReviewTarget)


# TestResult schemas
class TestResultBase(Base):
    test_configuration_id: UUID4
    test_run_id: Optional[UUID4] = None
    prompt_id: Optional[UUID4] = None
    test_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    test_metrics: Optional[Dict[str, Any]] = None
    test_reviews: Optional[Dict[str, Any]] = None
    test_output: Optional[Union[str, Dict[str, Any]]] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class TestResultCreate(TestResultBase):
    pass


class TestResultUpdate(TestResultBase):
    test_configuration_id: Optional[UUID4] = None


class TestResult(TestResultBase):
    last_review: Optional[Dict[str, Any]] = None
    matches_review: bool = False
    review_summary: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# Review schemas
class ReviewTargetCreate(Base):
    type: ReviewTarget = Field(
        ...,
        description="Type of target: 'test_result', 'trace', 'turn', or 'metric'",
    )
    reference: Optional[str] = Field(
        None,
        description=(
            "Reference name (metric name for 'metric', 'Turn N' for 'turn', null for 'test_result')"
        ),
    )

    @field_validator("type", mode="before")
    @classmethod
    def normalize_legacy_type(cls, v: str) -> str:
        if v == LEGACY_TARGET_TEST:
            return REVIEW_TARGET_TEST_RESULT
        return v


class ReviewCreate(Base):
    status_id: UUID4 = Field(..., description="Status UUID for this review")
    comments: str = Field(..., description="Review comments")
    target: ReviewTargetCreate = Field(
        ..., description="Target of the review (test or specific metric)"
    )


class ReviewUpdate(Base):
    status_id: Optional[UUID4] = Field(None, description="Updated status UUID")
    comments: Optional[str] = Field(None, description="Updated review comments")
    target: Optional[ReviewTargetCreate] = Field(None, description="Updated target")


class ReviewResponse(Base):
    review_id: str
    status: Dict[str, Any]
    user: Dict[str, Any]
    comments: str
    created_at: str
    updated_at: str
    target: Dict[str, Any]
