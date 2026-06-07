from typing import Optional
from uuid import UUID

from pydantic import UUID4, BaseModel, ConfigDict


class ProjectMemberCreate(BaseModel):
    user_id: UUID4
    role: Optional[str] = "member"
    role_id: Optional[UUID] = None


class ProjectMemberUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None
    picture: Optional[str] = None


class ProjectMember(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: UUID4
    user_id: UUID4
    organization_id: UUID4
    role: Optional[str] = "member"
    role_id: Optional[UUID] = None
    user: Optional[ProjectMemberUser] = None
