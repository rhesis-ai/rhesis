from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import UUID4, BaseModel, ConfigDict, ValidationError, field_validator

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.multi_turn_test_config import validate_multi_turn_config
from rhesis.backend.app.schemas.user import UserReference


# Base models for related entities
class UserBase(Base):
    id: UUID4

    model_config = ConfigDict(from_attributes=True)


class TypeLookup(Base):
    id: UUID4
    type_name: str
    type_value: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Topic(Base):
    id: UUID4
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Prompt(Base):
    id: UUID4
    content: str  # Changed from text to content based on your model

    model_config = ConfigDict(from_attributes=True)


class Status(Base):
    id: UUID4
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Behavior(Base):
    id: UUID4
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Category(Base):
    id: UUID4
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Source(Base):
    id: UUID4
    title: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TestTag(Base):
    id: UUID4
    name: str
    icon_unicode: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Test schemas
class TestBase(Base):
    prompt_id: UUID4
    test_set_id: Optional[UUID4] = None
    test_type_id: Optional[UUID4] = None
    priority: Optional[int] = None
    user_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    test_configuration: Optional[Dict] = None
    parent_id: Optional[UUID4] = None
    topic_id: Optional[UUID4] = None
    behavior_id: Optional[UUID4] = None
    category_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    source_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    test_metadata: Optional[Dict[str, Any]] = None


class TestCreate(TestBase):
    @field_validator("test_configuration")
    @classmethod
    def validate_test_configuration(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Validate test_configuration JSON based on content.

        For multi-turn tests (when goal is present), validates against MultiTurnTestConfig schema.
        """
        if v is None:
            return None

        # If 'goal' is present, this is a multi-turn test configuration
        if "goal" in v:
            try:
                # Validate using multi-turn config schema
                validated_config = validate_multi_turn_config(v)
                # Return as dict for storage
                return validated_config.model_dump(exclude_none=True)
            except ValidationError as e:
                # Re-raise with more context
                error_messages = []
                for error in e.errors():
                    field = " -> ".join(str(loc) for loc in error["loc"])
                    error_messages.append(f"{field}: {error['msg']}")
                raise ValueError(
                    f"Invalid multi-turn test configuration: {'; '.join(error_messages)}"
                )

        # For other configurations, allow any valid JSON
        return v


class TestUpdate(TestBase):
    prompt_id: Optional[UUID4] = None

    @field_validator("test_configuration")
    @classmethod
    def validate_test_configuration(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Validate test_configuration JSON based on content.

        For multi-turn tests (when goal is present), validates against MultiTurnTestConfig schema.
        """
        if v is None:
            return None

        # If 'goal' is present, this is a multi-turn test configuration
        if "goal" in v:
            try:
                # Validate using multi-turn config schema
                validated_config = validate_multi_turn_config(v)
                # Return as dict for storage
                return validated_config.model_dump(exclude_none=True)
            except ValidationError as e:
                # Re-raise with more context
                error_messages = []
                for error in e.errors():
                    field = " -> ".join(str(loc) for loc in error["loc"])
                    error_messages.append(f"{field}: {error['msg']}")
                raise ValueError(
                    f"Invalid multi-turn test configuration: {'; '.join(error_messages)}"
                )

        # For other configurations, allow any valid JSON
        return v


class Test(TestBase):
    id: UUID4
    created_at: Union[datetime, str]
    updated_at: Union[datetime, str]

    model_config = ConfigDict(from_attributes=True)


# The detailed model with expanded relations
class TestDetail(Test):
    # Include the full related objects instead of just IDs
    prompt: Optional[Prompt] = None
    test_type: Optional[TypeLookup] = None
    user: Optional[UserReference] = None
    assignee: Optional[UserReference] = None
    owner: Optional[UserReference] = None
    parent: Optional["TestDetail"] = None
    topic: Optional[Topic] = None
    behavior: Optional[Behavior] = None
    category: Optional[Category] = None
    status: Optional[Status] = None
    source: Optional[Source] = None
    tags: Optional[List[TestTag]] = []


# Bulk creation models
class TestPromptCreate(BaseModel):
    content: str
    language_code: str = "en"
    demographic: Optional[str] = None
    dimension: Optional[str] = None
    expected_response: Optional[str] = None


class TestBulkCreate(BaseModel):
    prompt: Optional[TestPromptCreate] = None  # Optional for Multi-Turn tests
    behavior: str
    category: str
    topic: str
    test_configuration: Optional[Dict[str, Any]] = None
    assignee_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    status: Optional[str] = None
    priority: Optional[int] = None

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


class TestBulkCreateRequest(BaseModel):
    tests: List[TestBulkCreate]
    test_set_id: Optional[UUID4] = None


class TestBulkResponse(BaseModel):
    id: UUID4
    prompt_id: UUID4
    test_type_id: UUID4
    priority: int
    user_id: UUID4
    topic_id: UUID4
    behavior_id: UUID4
    category_id: UUID4
    status_id: UUID4
    organization_id: UUID4
    test_configuration: Optional[Dict[str, Any]] = None
    prompt: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class TestBulkCreateResponse(BaseModel):
    success: bool
    total_tests: int
    message: str
