from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import UUID4, BaseModel, ConfigDict, field_validator

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.tag import Tag


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
    pass


class TestSetUpdate(TestSetBase):
    name: str = None


class TestSet(TestSetBase):
    id: UUID4
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]

    model_config = ConfigDict(from_attributes=True)


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
        from pydantic import ValidationError

        from rhesis.backend.app.schemas.multi_turn_test_config import validate_multi_turn_config

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

        # If 'goal' is present, validate as multi-turn config
        if "goal" in v:
            try:
                validated_config = validate_multi_turn_config(v)
                return validated_config.model_dump(exclude_none=True)
            except ValidationError as e:
                error_messages = []
                for error in e.errors():
                    field = " -> ".join(str(loc) for loc in error["loc"])
                    error_messages.append(f"{field}: {error['msg']}")
                raise ValueError(
                    f"Invalid multi-turn test configuration: {'; '.join(error_messages)}"
                )

        return v


class TestSetBulkCreate(BaseModel):
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    test_set_type: Optional[str] = None
    owner_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None
    priority: Optional[int] = None
    tests: List[TestData]
    metadata: Optional[Dict[str, Any]] = None

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
