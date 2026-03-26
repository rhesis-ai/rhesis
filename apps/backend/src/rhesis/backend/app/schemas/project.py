from typing import Any, Dict, Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


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
