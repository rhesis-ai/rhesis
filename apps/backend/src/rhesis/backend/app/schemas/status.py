from typing import Any, Dict, List, Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.tag import TagRead
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


# Lightweight reference schemas for the relationships exposed on StatusDetail.
# Local to this module (not exported) -- mirrors the TestDetail convention.
class TypeLookupReference(Base):
    id: UUID4
    description: Optional[str] = None
    type_name: Optional[str] = None
    type_value: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class ProjectReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[Dict[str, Any]] = None
    tags: Optional[List[TagRead]] = None
    icon: Optional[str] = None


class OrganizationReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None


# The detailed model with expanded relations
class StatusDetail(Status):
    entity_type: Optional[TypeLookupReference] = None
    project: Optional[ProjectReference] = None
    organization: Optional[OrganizationReference] = None
    user: Optional[UserReference] = None
