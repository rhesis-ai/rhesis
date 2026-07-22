from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.tag import Tag, TagRead
from rhesis.backend.app.schemas.user import UserReference as _BaseUserReference


class MetricsSource(str, Enum):
    """Enum for tracking the source of metrics used in a test execution."""

    BEHAVIOR = "behavior"
    TEST_SET = "test_set"
    EXECUTION_TIME = "execution_time"


# TestSet schemas
class TestSetBase(Base):
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    slug: Optional[str] = None
    status_id: Optional[UUID4] = None
    tags: Optional[List[Tag]] = []
    license_type_id: Optional[UUID4] = None
    test_set_type_id: Optional[UUID4] = None
    attributes: Optional[dict] = None
    user_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None
    priority: Optional[int] = 0
    is_published: Optional[bool] = False
    organization_id: Optional[UUID4] = None
    visibility: Optional[str] = None


class TestSetCreate(TestSetBase):
    test_set_type_id: UUID4


class ExplorerTestSetCreate(Base):
    """Request body for creating a test set for Explorer (test tree)."""

    name: str
    description: Optional[str] = None


class TestSetUpdate(TestSetBase):
    name: str = None


class TestSet(TestSetBase):
    id: UUID4
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]

    model_config = ConfigDict(from_attributes=True)


# Lightweight reference schemas for TestSetDetail's relationship fields.
# Mirrors the shape schema_factory.create_detailed_schema previously derived
# by reflection (see utils/schema_factory.py common_fields).
class StatusReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)


class TypeLookupReference(Base):
    id: UUID4
    description: Optional[str] = None
    type_name: Optional[str] = None
    type_value: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[Dict[str, Any]] = None
    tags: Optional[List[TagRead]] = None
    icon: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None

    model_config = ConfigDict(from_attributes=True)


class UserReference(_BaseUserReference):
    """Extends the shared UserReference with organization_id, which the
    schema_factory-generated reference for TestSet included."""

    organization_id: Optional[UUID4] = None


# The detailed model with expanded relations
class TestSetDetail(TestSet):
    id: UUID4
    nano_id: Optional[str]
    name: Optional[str] = None
    tags: Optional[List[TagRead]] = None
    attributes: Optional[Dict[str, Any]] = None
    counts: Optional[Dict[str, Any]] = None

    status: Optional[StatusReference] = None
    license_type: Optional[TypeLookupReference] = None
    test_set_type: Optional[TypeLookupReference] = None
    user: Optional[UserReference] = None
    owner: Optional[UserReference] = None
    assignee: Optional[UserReference] = None
    organization: Optional[OrganizationReference] = None
    project: Optional[ProjectReference] = None


# Bulk creation models
class TestPrompt(BaseModel):
    content: str
    language_code: str = "en"
    demographic: Optional[str] = None
    dimension: Optional[str] = None
    expected_response: Optional[str] = None


class TestData(BaseModel):
    prompt: Optional[TestPrompt] = None  # Optional for Multi-Turn tests
    behavior: str
    category: str
    topic: str
    test_type: Optional[str] = None
    test_configuration: Optional[Dict[str, Any]] = None
    assignee_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = {}

    @field_validator("test_type")
    @classmethod
    def validate_test_type(cls, v: Optional[str]) -> Optional[str]:
        from rhesis.backend.app.schemas.validators import format_test_type

        return format_test_type(v)

    @field_validator("assignee_id", "owner_id")
    @classmethod
    def validate_uuid(cls, v):
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return None
        # Additional validation for UUID format
        try:
            from uuid import UUID

            if isinstance(v, str):
                UUID(v)  # This will raise ValueError if invalid
            return v
        except (ValueError, TypeError):
            # If it's not a valid UUID, return None instead of raising an error
            return None

    @field_validator("test_configuration")
    @classmethod
    def validate_multi_turn_or_prompt(cls, v, info):
        """
        Validate that either:
        - prompt is provided (single-turn test), OR
        - test_configuration with goal is provided (multi-turn test)
        """

        prompt = info.data.get("prompt")

        # If prompt is provided, it's a single-turn test - OK
        if prompt:
            return v

        # If no prompt, must be multi-turn - validate goal exists
        if not v or not v.get("goal"):
            raise ValueError(
                "Either 'prompt' must be provided (for single-turn tests) "
                "or 'test_configuration' with 'goal' must be provided (for multi-turn tests)"
            )

        from rhesis.backend.app.schemas.validators import validate_test_config_content

        return validate_test_config_content(v)


class TestSetBulkCreate(BaseModel):
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    test_set_type: str
    owner_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None
    priority: Optional[int] = None
    project_id: Optional[UUID4] = None
    tests: List[TestData]
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("test_set_type")
    @classmethod
    def validate_test_set_type(cls, v: str) -> str:
        from rhesis.backend.app.schemas.validators import format_test_set_type

        return format_test_set_type(v)

    @field_validator("owner_id", "assignee_id")
    @classmethod
    def validate_uuid_fields(cls, v):
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return None
        # Additional validation for UUID format
        try:
            from uuid import UUID

            if isinstance(v, str):
                UUID(v)  # This will raise ValueError if invalid
            return v
        except (ValueError, TypeError):
            # If it's not a valid UUID, return None instead of raising an error
            return None


class TestSetBulkResponse(BaseModel):
    id: UUID4
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    status_id: Optional[UUID4] = None
    license_type_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    visibility: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class TestSetBulkAssociateRequest(BaseModel):
    test_ids: List[UUID4]


class TestSetBulkAssociateResponse(BaseModel):
    success: bool
    total_tests: int
    message: str
    metadata: Dict[str, Any] = {
        "new_associations": None,
        "existing_associations": None,
        "invalid_associations": None,
        "existing_test_ids": None,
        "invalid_test_ids": None,
    }

    model_config = ConfigDict(from_attributes=True)


class TestSetBulkDisassociateRequest(BaseModel):
    test_ids: List[UUID4]


class TestSetBulkDisassociateResponse(BaseModel):
    success: bool
    total_tests: int
    removed_associations: int
    message: str


class ExecutionMetric(BaseModel):
    """Metric specification for execution-time metric override.

    When specified at execution time, these metrics completely override
    test set metrics and behavior metrics.
    """

    id: UUID4
    name: str
    scope: Optional[List[str]] = None  # e.g., ["Single-Turn"], ["Multi-Turn"], or both


class TestSetExecutionRequest(BaseModel):
    """Request model for test set execution with flexible execution options."""

    execution_options: Optional[Dict[str, Any]] = None
    metrics: Optional[List[ExecutionMetric]] = None
    reference_test_run_id: Optional[UUID4] = None
    execution_model_id: Optional[UUID4] = None
    evaluation_model_id: Optional[UUID4] = None
    experiment_id: Optional[UUID4] = Field(
        default=None,
        description=(
            "When set (optionally with version / environment), intent is stored on the "
            "created test configuration and resolved into a run snapshot at queue "
            "time. Omit experiment_id, version, and environment for legacy executions."
        ),
    )
    version: Optional[str] = None
    environment: Optional[str] = None

    @field_validator("execution_options")
    @classmethod
    def validate_execution_options(cls, v):
        if v is None:
            return {"execution_mode": "Parallel"}

        # Validate execution_mode if provided
        if "execution_mode" in v and v["execution_mode"] not in ["Parallel", "Sequential"]:
            raise ValueError('execution_mode must be either "Parallel" or "Sequential"')

        # Set default execution_mode if not provided
        if "execution_mode" not in v:
            v["execution_mode"] = "Parallel"

        return v


class TestRunRescoreRequest(BaseModel):
    """Request to re-score a test run with different metrics.

    No endpoints will be invoked -- only metric evaluation on stored outputs.
    """

    metrics: Optional[List[ExecutionMetric]] = None
    execution_options: Optional[Dict[str, Any]] = None
    evaluation_model_id: Optional[UUID4] = None
