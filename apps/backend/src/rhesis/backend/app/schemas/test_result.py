from typing import Any, ClassVar, Dict, List, Optional, Union

from pydantic import UUID4, ConfigDict, Field, field_validator

from rhesis.backend.app.auth.capabilities import ResourceType
from rhesis.backend.app.constants import (
    LEGACY_TARGET_TEST,
    REVIEW_TARGET_TEST_RESULT,
    ReviewTarget,
)
from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.affordances import WithPermittedActions
from rhesis.backend.app.schemas.references import (
    BehaviorReference,
    OrganizationReference,
    ProjectReference,
    PromptReference,
    StatusReference,
    TopicReference,
)
from rhesis.backend.app.schemas.tag import TagRead
from rhesis.backend.app.schemas.user import UserReference

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


class TestResult(TestResultBase, WithPermittedActions):
    """Full TestResult response with server-resolved object-level affordances.

    ``permitted_actions`` is populated automatically during serialization for
    the calling principal — see :class:`WithPermittedActions`.
    """

    __resource_type__: ClassVar[Optional[str]] = ResourceType.TEST_RESULT
    # __owner_attr__ defaults to "user_id", which is correct for TestResult.

    last_review: Optional[Dict[str, Any]] = None
    matches_review: bool = False
    review_summary: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# Lightweight reference schemas below are specific to TestResultDetail's
# nested chain (test -> prompt / behavior / topic) -- richer than the shared
# references, so they stay local rather than living in schemas/references.py.
class TestReference(Base):
    id: UUID4
    content: Optional[str] = None
    counts: Optional[Dict[str, Any]] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None
    prompt: Optional[PromptReference] = None
    behavior: Optional[BehaviorReference] = None
    topic: Optional[TopicReference] = None

    model_config = ConfigDict(from_attributes=True)


class TestConfigurationReference(Base):
    id: UUID4
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[Dict[str, Any]] = None
    endpoint_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)


class TestRunReference(Base):
    id: UUID4
    name: Optional[str] = None
    counts: Optional[Dict[str, Any]] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[Dict[str, Any]] = None
    experiment_summary: Optional[Dict[str, Any]] = None
    tags: Optional[List[TagRead]] = None

    model_config = ConfigDict(from_attributes=True)


class TestResultDetail(TestResult):
    id: UUID4
    nano_id: Optional[str]
    counts: Optional[Dict[str, Any]] = None
    tags: Optional[List[TagRead]] = None
    status: Optional[StatusReference] = None
    user: Optional[UserReference] = None
    test: Optional[TestReference] = None
    test_configuration: Optional[TestConfigurationReference] = None
    test_run: Optional[TestRunReference] = None
    organization: Optional[OrganizationReference] = None
    project: Optional[ProjectReference] = None


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
    resolved: Optional[bool] = Field(None, description="Mark the review as resolved or reopen it")


class ReviewResponse(Base):
    review_id: str
    status: Dict[str, Any]
    user: Dict[str, Any]
    comments: str
    created_at: str
    updated_at: str
    target: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[str] = None
    resolved_by: Optional[Dict[str, Any]] = None
    permitted_actions: List[str] = Field(default_factory=list)
