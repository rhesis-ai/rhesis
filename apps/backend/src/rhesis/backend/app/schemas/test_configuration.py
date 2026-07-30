from typing import Any, Dict, List, Optional

from pydantic import UUID4, BaseModel, Field

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.tag import TagRead


# TestConfiguration schemas
class TestConfigurationBase(Base):
    endpoint_id: UUID4
    category_id: Optional[UUID4] = None
    topic_id: Optional[UUID4] = None
    prompt_id: Optional[UUID4] = None
    use_case_id: Optional[UUID4] = None
    test_set_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[dict] = None


class TestConfigurationCreate(TestConfigurationBase):
    pass


class TestConfigurationUpdate(TestConfigurationBase):
    endpoint_id: Optional[UUID4] = None


class TestConfiguration(TestConfigurationBase):
    pass


class TestSetReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    counts: Optional[Dict[str, Any]] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[Dict[str, Any]] = None
    tags: Optional[List[TagRead]] = None


class EndpointReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None


# The detailed model with expanded relations
class TestConfigurationDetail(TestConfiguration):
    # The factory-generated schema overrides endpoint_id to Optional (the
    # base schema declares it required) -- preserved here for parity.
    id: UUID4
    endpoint_id: Optional[UUID4] = None
    test_set: Optional[TestSetReference] = None
    endpoint: Optional[EndpointReference] = None


class TestConfigurationExecutionRequest(BaseModel):
    """Request model for test configuration execution."""

    experiment_id: Optional[UUID4] = Field(
        default=None,
        description=(
            "When set (optionally with version / environment), intent is stored on the "
            "test configuration and resolved into a run snapshot at queue time."
        ),
    )
    version: Optional[str] = None
    environment: Optional[str] = None
