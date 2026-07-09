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
# User summary (for enriched org-member responses)
# ---------------------------------------------------------------------------


class UserSummary(BaseModel):
    """Minimal user fields for the team members grid."""

    id: UUID
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    email: str
    picture: Optional[str] = None
    auth0_id: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Organization member role assignment
# ---------------------------------------------------------------------------


class OrgMemberRead(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    role_id: UUID
    role: Optional[RoleRead] = None
    user: Optional[UserSummary] = None
    #: Capability strings the caller may exercise on THIS member (e.g.
    #: "member:manage", "member:delete"), server-resolved by the router.
    #: Encodes the privilege-escalation guard (self-change and outranking
    #: are both denied) so the frontend never re-derives it. See
    #: `_member_permitted_actions` in router.py.
    permitted_actions: list[str] = Field(default_factory=list)

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
    #: Capability strings the caller may exercise on THIS member (e.g.
    #: "member:manage"), server-resolved by the router. Encodes the
    #: privilege-escalation guard (self-change and outranking are both
    #: denied) so the frontend never re-derives it. See
    #: `_member_permitted_actions` in router.py.
    permitted_actions: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Bulk user-project membership (single-call alternative to N per-project fetches)
# ---------------------------------------------------------------------------


class ProjectSummary(BaseModel):
    """Minimal project fields needed by the Member Access drawer."""

    id: UUID
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None

    model_config = {"from_attributes": True}


class UserProjectMembershipRead(BaseModel):
    """A user's membership in a single project, including project summary and role."""

    project_id: UUID
    user_id: UUID
    role_id: Optional[UUID] = None
    role: Optional[RoleRead] = None
    project: ProjectSummary

    model_config = {"from_attributes": True}


__all__ = [
    "OrgMemberRead",
    "OrgRoleAssign",
    "PermissionRead",
    "UserSummary",
    "ProjectMemberRoleAssign",
    "ProjectMemberRoleRead",
    "ProjectSummary",
    "RoleCreate",
    "RoleRead",
    "RoleUpdate",
    "UserProjectMembershipRead",
]
