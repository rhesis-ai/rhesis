from typing import Any, Dict, List, Optional

from pydantic import UUID4, ConfigDict

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.tag import TagRead
from rhesis.backend.app.schemas.user import UserReference as _BaseUserReference


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


# Lightweight reference schemas for CategoryDetail's relationship fields.
# Mirrors the shape schema_factory.create_detailed_schema previously derived
# by reflection (see utils/schema_factory.py common_fields).
class StatusReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)


class CategoryReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    counts: Optional[Dict[str, Any]] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    status_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)


class TypeLookupReference(Base):
    id: UUID4
    description: Optional[str] = None
    type_name: Optional[str] = None
    type_value: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class OrganizationReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None

    model_config = ConfigDict(from_attributes=True)


class UserReference(_BaseUserReference):
    """Extends the shared UserReference with organization_id, which the
    schema_factory-generated reference for Category included."""

    organization_id: Optional[UUID4] = None


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
