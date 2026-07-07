"""Pydantic schemas for the EE RBAC role and assignment APIs (SP8)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------


class PermissionRead(BaseModel):
    id: UUID
    name: str
    display_name: str
    resource_type: str
    action: str
    scope: str
    is_retired: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------


class RoleRead(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: str = ""
    scope: str
    level: int
    is_built_in: bool
    organization_id: Optional[UUID] = None
    permissions: list[PermissionRead] = Field(default_factory=list)
    member_count: int = Field(
        default=0,
        description="Number of distinct users holding this role (org + project assignments).",
    )

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    """Create an org-scoped custom role."""

    name: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(default="", max_length=128)
    description: str = Field(default="", max_length=512)
    scope: str = Field(default="organization", pattern="^(organization|project)$")
    permission_names: list[str] = Field(
        default_factory=list,
        description="Capability strings to include, e.g. ['test_set:read', 'test:create'].",
    )


class RoleUpdate(BaseModel):
    """Update a custom role (built-in roles are immutable)."""

    display_name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field(None, max_length=512)
    permission_names: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# Organization member role assignment
# ---------------------------------------------------------------------------


class OrgMemberRead(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    role_id: UUID
    role: Optional[RoleRead] = None

    model_config = {"from_attributes": True}


class OrgRoleAssign(BaseModel):
    """Assign or update the org-level role for a user."""

    role_id: UUID = Field(..., description="ID of the role to assign.")


# ---------------------------------------------------------------------------
# Project member role assignment
# ---------------------------------------------------------------------------


class ProjectMemberRoleAssign(BaseModel):
    """Assign or update the project-level role for a user."""

    role_id: UUID = Field(..., description="ID of the role to assign.")


class ProjectMemberRoleRead(BaseModel):
    """Response schema for project-level role assignment."""

    project_id: UUID
    user_id: UUID
    role_id: Optional[UUID] = None
    role: Optional[RoleRead] = None

    model_config = {"from_attributes": True}


__all__ = [
    "OrgMemberRead",
    "OrgRoleAssign",
    "PermissionRead",
    "ProjectMemberRoleAssign",
    "ProjectMemberRoleRead",
    "RoleCreate",
    "RoleRead",
    "RoleUpdate",
]
