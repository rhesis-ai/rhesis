from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# TestRun schemas
class TestRunBase(Base):
    name: Optional[str] = None
    user_id: Optional[UUID4]
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[dict] = None
    test_configuration_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None


class TestRunCreate(TestRunBase):
    pass


class TestRunUpdate(TestRunBase):
    user_id: Optional[UUID4] = None
    pass


class TestRun(TestRunBase):
    pass
