from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.references import (
    OrganizationReference,
    ProjectReference,
    StatusReference,
    TopicReference,
    TypeLookupReference,
)
from rhesis.backend.app.schemas.user import UserReference


# Topic schemas
class TopicBase(Base):
    name: str
    description: Optional[str] = None
    parent_id: Optional[UUID4] = None
    entity_type_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None


class TopicCreate(TopicBase):
    pass


class TopicUpdate(TopicBase):
    name: Optional[str] = None


class Topic(TopicBase):
    pass


# The detailed model with expanded relations
class TopicDetail(Topic):
    id: UUID4
    name: Optional[str] = None

    status: Optional[StatusReference] = None
    parent: Optional[TopicReference] = None
    entity_type: Optional[TypeLookupReference] = None
    project: Optional[ProjectReference] = None
    organization: Optional[OrganizationReference] = None
    user: Optional[UserReference] = None
