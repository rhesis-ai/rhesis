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
    REQUIREMENT = "Requirement"
    CATEGORY = "Category"
    ENDPOINT = "Endpoint"
    PROJECT = "Project"
    ORGANIZATION = "Organization"
    MODEL = "Model"
    METRIC = "Metric"
    TRACE = "Trace"


class TagRead(Base):
    id: UUID4
    name: str
    icon_unicode: Optional[str] = None


class Tag(TagBase):
    pass
