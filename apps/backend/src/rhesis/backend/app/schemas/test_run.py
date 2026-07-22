from typing import Any, ClassVar, Dict, List, Optional

from pydantic import UUID4, ConfigDict

from rhesis.backend.app.auth.capabilities import ResourceType
from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.affordances import WithPermittedActions
from rhesis.backend.app.schemas.references import (
    OrganizationReference,
    ProjectReference,
    StatusReference,
    TypeLookupReference,
)
from rhesis.backend.app.schemas.tag import TagRead
from rhesis.backend.app.schemas.user import UserReference


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


# Lightweight reference schemas below are specific to TestRunDetail's nested
# chain (test_configuration -> endpoint -> project, test_configuration ->
# test_set -> test_set_type) -- richer than the shared references, so they
# stay local rather than living in schemas/references.py.
class ExperimentReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)


class EndpointReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None
    project: Optional[ProjectReference] = None

    model_config = ConfigDict(from_attributes=True)


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
    test_set_type: Optional[TypeLookupReference] = None

    model_config = ConfigDict(from_attributes=True)


class TestConfigurationReference(Base):
    id: UUID4
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[Dict[str, Any]] = None
    endpoint_id: Optional[UUID4] = None
    endpoint: Optional[EndpointReference] = None
    test_set: Optional[TestSetReference] = None

    model_config = ConfigDict(from_attributes=True)


class TestRunDetail(TestRun):
    id: UUID4
    nano_id: Optional[str]
    counts: Optional[Dict[str, Any]] = None
    experiment_summary: Optional[Dict[str, Any]] = None
    tags: Optional[List[TagRead]] = None
    status: Optional[StatusReference] = None
    assignee: Optional[UserReference] = None
    owner: Optional[UserReference] = None
    user: Optional[UserReference] = None
    experiment: Optional[ExperimentReference] = None
    test_configuration: Optional[TestConfigurationReference] = None
    organization: Optional[OrganizationReference] = None
    project: Optional[ProjectReference] = None
