from typing import ClassVar, Optional

from pydantic import UUID4, ConfigDict

from rhesis.backend.app.auth.capabilities import ResourceType
from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.affordances import WithPermittedActions


# TestRun schemas
class TestRunBase(Base):
    name: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[dict] = None
    test_configuration_id: UUID4
    experiment_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None


class TestRunCreate(TestRunBase):
    pass


class TestRunUpdate(TestRunBase):
    user_id: Optional[UUID4] = None
    test_configuration_id: Optional[UUID4] = None
    pass


class TestRun(TestRunBase, WithPermittedActions):
    """Full TestRun response with server-resolved object-level affordances.

    ``permitted_actions`` is populated automatically during serialization for
    the calling principal — see :class:`WithPermittedActions`.
    """

    __resource_type__: ClassVar[Optional[str]] = ResourceType.TEST_RUN
    # __owner_attr__ defaults to "user_id", which is the creator column on TestRun.

    model_config = ConfigDict(from_attributes=True)
