from typing import Dict, Optional

from pydantic import UUID4, ConfigDict

from rhesis.backend.app.schemas import Base


# TestContext schemas
class TestContextBase(Base):
    test_id: UUID4
    entity_id: UUID4
    entity_type: str
    attributes: Optional[Dict] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


class TestContextCreate(TestContextBase):
    pass


class TestContextUpdate(TestContextBase):
    test_id: Optional[UUID4] = None
    entity_id: Optional[UUID4] = None
    entity_type: Optional[str] = None


class TestContext(TestContextBase):
    id: UUID4
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)
