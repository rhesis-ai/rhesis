from typing import Any, Dict, List, Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.tag import TagRead
from rhesis.backend.app.schemas.user import UserReference


# Project schemas
class ProjectBase(Base):
    name: str
    description: Optional[str] = None
    is_active: Optional[bool] = True
    user_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    icon: Optional[str] = None
    status_id: Optional[UUID4] = None
    attributes: Optional[Dict[str, Any]] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ProjectBase):
    name: Optional[str] = None


class Project(ProjectBase):
    id: UUID4


# Lightweight reference schemas for the relationships exposed on ProjectDetail.
# Local to this module (not exported) -- mirrors the TestDetail convention.
class StatusReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None


class OrganizationReference(Base):
    id: UUID4
    name: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[UUID4] = None
    tags: Optional[List[TagRead]] = None


# The detailed model with expanded relations
class ProjectDetail(Project):
    tags: Optional[List[TagRead]] = None
    user: Optional[UserReference] = None
    owner: Optional[UserReference] = None
    organization: Optional[OrganizationReference] = None
    status: Optional[StatusReference] = None
