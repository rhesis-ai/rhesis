from typing import Any, ClassVar, Dict, List, Optional, Union

from pydantic import UUID4, ConfigDict, Field, field_validator

from rhesis.backend.app.auth.capabilities import ResourceType
from rhesis.backend.app.constants import (
    LEGACY_TARGET_TEST,
    REVIEW_TARGET_TEST_RESULT,
    ReviewTarget,
)
from rhesis.backend.app.schemas.affordances import WithPermittedActions
from rhesis.backend.app.schemas.base import Base, ServerIdentity
from rhesis.backend.app.schemas.references import (
    PromptReference,
    RequirementReference,
)
from rhesis.backend.app.schemas.tag import TagRead

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
    # Source of truth for aggregation -- see app/outcomes.py.
    #
    # ``execution`` defaults to "not_run" rather than None: create_item's
    # full model_dump() (not exclude_unset) means an un-set field is still
    # written as an explicit value, and the column is NOT NULL. A create
    # call site that doesn't set this explicitly is wrong (it should -- see
    # jobs/execution/executors/results.py for the pattern), but it must
    # fail safe as "never ran" rather than raise IntegrityError on every
    # untouched write path.
    execution: str = "not_run"
    verdict: Optional[str] = None
    test_metrics: Optional[Dict[str, Any]] = None
    test_reviews: Optional[Dict[str, Any]] = None
    test_output: Optional[Union[str, Dict[str, Any]]] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class TestResultCreate(TestResultBase):
    pass


class TestResultUpdate(TestResultBase):
    test_configuration_id: Optional[UUID4] = None


class TestResult(TestResultBase, WithPermittedActions, ServerIdentity):
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


class TestReference(Base, ServerIdentity):
    id: UUID4
    prompt: Optional[PromptReference] = None
    requirement: Optional[RequirementReference] = None

    model_config = ConfigDict(from_attributes=True)


class TestRunReference(Base, ServerIdentity):
    id: UUID4
    name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TestResultDetail(TestResult):
    id: UUID4
    tags: Optional[List[TagRead]] = None
    test: Optional[TestReference] = None
    test_run: Optional[TestRunReference] = None
    # TestResult carries CountsMixin but nothing serialized it, so the Tests tab's
    # comment/task filters (test.counts?.comments/.tasks) read an undefined field.
    # Declared here rather than on TestResult: the read paths that return this schema
    # eager-load comments/tasks/files (see crud/test_result.py), while the create/
    # update/delete routes return the base schema off a row with no eager loads, where
    # serializing counts would lazy-load all three relationships per response.
    counts: Optional[Dict[str, Any]] = None


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
    permitted_actions: List[str] = Field(default_factory=list)
