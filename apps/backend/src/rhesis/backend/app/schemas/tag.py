from enum import Enum
from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# Tag schemas
class TagBase(Base):
    name: str
    icon_unicode: Optional[str] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


class TagCreate(TagBase):
    pass


class TagUpdate(TagBase):
    name: Optional[str] = None


class EntityType(str, Enum):
    SOURCE = "Source"
    TEST = "Test"
    TEST_SET = "TestSet"
    TEST_RUN = "TestRun"
    TEST_RESULT = "TestResult"
    PROMPT = "Prompt"
    PROMPT_TEMPLATE = "PromptTemplate"
    BEHAVIOR = "Behavior"
    CATEGORY = "Category"
    ENDPOINT = "Endpoint"
    USE_CASE = "UseCase"
    RESPONSE_PATTERN = "ResponsePattern"
    PROJECT = "Project"
    ORGANIZATION = "Organization"
    MODEL = "Model"
    METRIC = "Metric"


class TagAssignment(Base):
    entity_id: UUID4
    entity_type: EntityType


class TagRead(Base):
    id: UUID4
    name: str
    icon_unicode: Optional[str] = None


class Tag(TagBase):
    pass
