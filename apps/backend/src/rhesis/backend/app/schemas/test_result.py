from typing import Any, Dict, Optional, Union

from pydantic import UUID4, ConfigDict, Field

from rhesis.backend.app.schemas import Base


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

    model_config = ConfigDict(from_attributes=True)


# Review schemas
class ReviewTargetCreate(Base):
    type: str = Field(..., description="Type of target: 'test' or 'metric'")
    reference: Optional[str] = Field(
        None, description="Reference name (metric name or null for test)"
    )


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
