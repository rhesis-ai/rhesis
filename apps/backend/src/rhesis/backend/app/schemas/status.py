from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.references import (
    OrganizationReference,
    ProjectReference,
    TypeLookupReference,
)
from rhesis.backend.app.schemas.user import UserReference


# Status schemas
class StatusBase(Base):
    name: str
    description: Optional[str] = None
    entity_type_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class StatusCreate(StatusBase):
    pass


class StatusUpdate(StatusBase):
    name: Optional[str] = None


class Status(StatusBase):
    pass


# The detailed model with expanded relations
class StatusDetail(Status):
    id: UUID4
    name: Optional[str] = None
    entity_type: Optional[TypeLookupReference] = None
    project: Optional[ProjectReference] = None
    organization: Optional[OrganizationReference] = None
    user: Optional[UserReference] = None
