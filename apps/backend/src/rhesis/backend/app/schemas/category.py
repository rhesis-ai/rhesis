from typing import Any, Dict, Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.references import (
    CategoryReference,
    OrganizationReference,
    ProjectReference,
    StatusReference,
    TypeLookupReference,
)
from rhesis.backend.app.schemas.user import UserReference


# Category schemas
class CategoryBase(Base):
    name: str
    description: Optional[str] = None
    parent_id: Optional[UUID4] = None
    entity_type_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    name: Optional[str] = None


class Category(CategoryBase):
    pass


# The detailed model with expanded relations
class CategoryDetail(Category):
    id: UUID4
    nano_id: Optional[str]
    name: Optional[str] = None
    counts: Optional[Dict[str, Any]] = None
    status: Optional[StatusReference] = None
    parent: Optional[CategoryReference] = None
    entity_type: Optional[TypeLookupReference] = None
    project: Optional[ProjectReference] = None
    organization: Optional[OrganizationReference] = None
    user: Optional[UserReference] = None
