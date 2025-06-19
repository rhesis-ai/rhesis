from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


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
