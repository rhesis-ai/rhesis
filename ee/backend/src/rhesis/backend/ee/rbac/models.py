"""EE RBAC ORM models — role catalog, permission catalog, and org membership.

Four tables added in SP7 Alembic migration
``d9e0f1a2b3c4_add_rbac_catalog_tables``:

``permission``
    One row per ``resource:action`` capability string.  Seeded idempotently
    from :func:`~rhesis.backend.app.auth.capabilities.get_all_capabilities`
    at startup.  ``is_retired`` is set (never deleted) when a capability
    disappears from the registry so historical role assignments remain
    auditable.

``role``
    Defines a named role.  ``organization_id IS NULL`` → built-in (global);
    ``organization_id IS NOT NULL`` → org-owned custom role.
    ``scope ∈ {'organization', 'project'}`` reflects whether the role is
    assignable at the org tier (``organization_member``) or only at the
    project tier (``project_membership``).

``role_permission``
    Many-to-many join between ``role`` and ``permission``.  Built-in roles
    are recomputed by the startup sync; custom roles are never auto-modified
    (fail-closed for new capabilities).

``organization_member``
    Org-level role assignment for a user.  Project-level role assignment
    stays in the existing ``project_membership.role_id`` FK column (SP6).
    Resolution order (SP8): project role overrides org role; within a role,
    permissions are additive.

Dependency note
---------------
These models import from ``rhesis.backend.app.models.base``.  That is the
only permitted cross-boundary import direction (EE → core); core must never
import from ``rhesis.backend.ee.*``.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.guid import GUID

# ---------------------------------------------------------------------------
# Scope constants
# ---------------------------------------------------------------------------

SCOPE_ORGANIZATION = "organization"
SCOPE_PROJECT = "project"

# Canonical built-in role names (order encodes precedence: highest first).
BUILT_IN_ROLE_NAMES: tuple[str, ...] = ("Owner", "Admin", "Member", "Viewer", "None")

# Level values for built-in roles (higher = more privileged).
BUILT_IN_ROLE_LEVELS: dict[str, int] = {
    "Owner": 100,
    "Admin": 80,
    "Member": 60,
    "Viewer": 40,
    "None": 0,
}

# One-sentence descriptions shown on the Roles settings page.
# Backfilled by migration a2b3c4d5e6f7; kept here so all built-in role
# constants are co-located and reviewable without opening a migration file.
BUILT_IN_ROLE_DESCRIPTIONS: dict[str, str] = {
    "Owner": (
        "Complete control of the organization, including billing, "
        "deletion, and ownership transfer."
    ),
    "Admin": (
        "Manage members, roles, projects, and organization settings. "
        "Cannot delete the organization."
    ),
    "Member": (
        "Create, edit, and run evaluations across their projects. "
        "Manage their own API tokens."
    ),
    "Viewer": (
        "Read-only access to all resources. Can browse and export "
        "but cannot make changes."
    ),
    "None": "No access. Explicitly revoke a member while keeping them in the organization.",
}

# Resource types whose permissions are org-scoped.
_ORG_SCOPED_RESOURCES: frozenset[str] = frozenset(
    {
        "organization",
        "member",
        "role",
        "token",
        "recycle",
        "sso",
        "api_clients",
    }
)


def capability_scope(cap: str) -> str:
    """Return ``'organization'`` or ``'project'`` for a capability string.

    ``project:create`` is org-scoped (creating a project *inside* the org).
    All other ``project:*`` capabilities (read, update) are project-scoped.
    """
    parts = cap.split(":", 1)
    resource = parts[0]
    action = parts[1] if len(parts) > 1 else ""
    if resource in _ORG_SCOPED_RESOURCES:
        return SCOPE_ORGANIZATION
    if resource == "project" and action == "create":
        return SCOPE_ORGANIZATION
    return SCOPE_PROJECT


# Actions a **Member** may perform on any project-scoped resource.  Unlike the
# old hand-maintained resource allowlist, Member now covers *every* resource
# that :func:`capability_scope` classifies as project-scoped, so new project
# entities are usable by Members without editing this module.
_MEMBER_ACTIONS: frozenset[str] = frozenset(
    {"read", "create", "update", "delete", "execute", "generate", "import", "react"}
)


def _primary_action(cap: str) -> str:
    """Return the primary action component of *cap*, stripping any object qualifier.

    ``comment:update:own`` → ``"update"``; ``task:update:assigned`` → ``"update"``;
    ``test_set:read`` → ``"read"``.
    Used by :func:`_member_permissions` so that object-level-qualified capabilities
    (e.g. ``:own``, ``:assigned``) are treated the same as their unqualified
    counterparts when deciding which roles receive them.
    """
    parts = cap.split(":")
    # Three-part caps end with an object qualifier like "own" or "assigned".
    if len(parts) >= 3 and parts[-1] in ("own", "assigned"):
        return parts[-2]
    return parts[-1] if len(parts) >= 2 else cap


# Org-level reads excluded from the read-only **Viewer** baseline.
# ``role:read`` exposes the org's custom role catalog; only Owner and Admin
# need it (Admin needs it to assign roles via member:manage).  ``token:read``
# exposes API token metadata.  Everything else ending in ``:read`` — including
# ``organization:read`` and ``member:read`` for basic org context — is fine
# for a Viewer.
_VIEWER_EXCLUDED_READS: frozenset[str] = frozenset({"role:read", "token:read"})


def _viewer_permissions(cap_set: set[str]) -> set[str]:
    """Read-only baseline: every ``:read`` capability except sensitive org-admin
    reads (:data:`_VIEWER_EXCLUDED_READS`), plus ``recycle:view``."""
    reads = {c for c in cap_set if c.endswith(":read")} - _VIEWER_EXCLUDED_READS
    if "recycle:view" in cap_set:
        reads.add("recycle:view")
    return reads


def _member_permissions(cap_set: set[str]) -> set[str]:
    """Everything a Viewer can do, plus create/update/delete and the special
    project actions on **every** project-scoped resource.

    Unioning the Viewer set guarantees ``Member ⊇ Viewer`` by construction, so a
    higher-level role can never read less than a lower one.
    """
    project_actions = {
        c
        for c in cap_set
        if capability_scope(c) == SCOPE_PROJECT and _primary_action(c) in _MEMBER_ACTIONS
    }
    return project_actions | _viewer_permissions(cap_set)


def permissions_for_built_in_role(role_name: str, capabilities: list[str]) -> set[str]:
    """Compute the permission set for a built-in role from the capability catalog.

    Called by
    :meth:`~rhesis.backend.ee.rbac.provider.PermissionAuthorizationProvider._role_has_permission`
    (and ``get_effective_permissions``) to resolve a built-in role's permissions
    from code at request time — no ``role_permission`` rows are stored for
    built-in roles.

    Rules (locked in plan §2.2, Viewer/Member revised after SP8 review):
    - **Owner**  (level 100): all permissions.
    - **Admin**  (level 80): all except EE-only management (role:manage,
      role:read, sso:manage, api_clients:manage).
    - **Member** (level 60): Viewer plus :create/:update/:delete and the special
      project actions (:execute, :generate, :import, :react) on every
      project-scoped resource.
    - **Viewer** (level 40): every :read except role:read/token:read, plus
      recycle:view (covers organization:read and member:read for org context).
    - **None**   (level 0): no permissions.

    The definitions nest (Owner ⊇ Admin ⊇ Member ⊇ Viewer ⊇ None) so a
    higher-level built-in role never holds fewer permissions than a lower one;
    the SP7 catalog tests assert this invariant against the live catalog.

    Any name not in the built-in set returns an empty set (fail-closed).
    """
    cap_set = set(capabilities)

    match role_name:
        case "Owner":
            return cap_set
        case "Admin":
            # role:read is included so Admins can see the role catalog when
            # assigning roles via member:manage. role:manage (create/update/delete
            # custom roles) remains Owner-only.
            excluded = {"role:manage", "sso:manage", "api_clients:manage"}
            return cap_set - excluded
        case "Member":
            return _member_permissions(cap_set)
        case "Viewer":
            return _viewer_permissions(cap_set)
        case "None":
            return set()
        case _:
            return set()


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------


class Permission(Base):
    """One row per ``resource:action`` capability string.

    Seeded from the capability registry at startup; ``is_retired`` is set when
    a capability disappears from the registry (rows are never hard-deleted so
    historical ``role_permission`` rows remain auditable).
    """

    __tablename__ = "permission"

    #: Capability string, e.g. ``"test_set:read"``.  Globally unique.
    name = Column(String, nullable=False, unique=True, index=True)
    #: Human-readable label for the UI (e.g. ``"Read test sets"``).
    display_name = Column(String, nullable=False, default="")
    #: Resource type derived from the capability, e.g. ``"test_set"``.
    resource_type = Column(String, nullable=False, default="", index=True)
    #: Action derived from the capability, e.g. ``"read"``.
    action = Column(String, nullable=False, default="")
    #: ``'organization'`` or ``'project'``.
    scope = Column(String, nullable=False, default=SCOPE_PROJECT)
    #: Set to ``True`` when the capability is removed from the registry.
    #: Never hard-deleted so historical assignments stay auditable.
    is_retired = Column(Boolean, nullable=False, default=False, server_default="false")

    # Relationships
    role_permissions = relationship(
        "RolePermission", back_populates="permission", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Permission name={self.name!r} scope={self.scope!r}>"


class Role(Base):
    """A named role, either built-in (global) or org-owned custom.

    ``organization_id IS NULL`` — built-in; always present, never deleted.
    ``organization_id IS NOT NULL`` — org-owned custom role (Phase 2, SP8).
    """

    __tablename__ = "role"

    #: Short identifier, e.g. ``"Owner"``, ``"Admin"``.
    name = Column(String, nullable=False)
    #: Human-readable label for the UI.
    display_name = Column(String, nullable=False, default="")
    #: One-sentence description shown in the Roles settings page.
    #: Built-in roles are seeded by migration a2b3c4d5e6f7; custom roles
    #: default to '' and may be set via the create/update API.
    description = Column(Text, nullable=False, server_default="")
    #: ``'organization'`` — assignable at org tier via ``organization_member``.
    #: ``'project'``      — assignable at project tier via ``project_membership``.
    scope = Column(String, nullable=False, default=SCOPE_PROJECT)
    #: Privilege level (higher = more privileged). Built-ins: Owner=100, …, None=0.
    level = Column(Integer, nullable=False, default=0)
    #: True for the five built-in roles; False for org-owned custom roles.
    is_built_in = Column(Boolean, nullable=False, default=False, server_default="false")
    #: ``NULL`` for built-in roles; set for org-owned custom roles.
    organization_id = Column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        # Built-in role names are globally unique (org IS NULL).
        # Custom role names must be unique per org.
        Index(
            "ix_role_name_org",
            "name",
            "organization_id",
            unique=True,
        ),
    )

    # Relationships
    role_permissions = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan"
    )
    organization_members = relationship("OrganizationMember", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role name={self.name!r} built_in={self.is_built_in} level={self.level}>"


class RolePermission(Base):
    """Many-to-many join between :class:`Role` and :class:`Permission`."""

    __tablename__ = "role_permission"

    role_id = Column(
        GUID(),
        ForeignKey("role.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id = Column(
        GUID(),
        ForeignKey("permission.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    # Relationships
    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    def __repr__(self) -> str:
        return f"<RolePermission role_id={self.role_id} permission_id={self.permission_id}>"


class OrganizationMember(Base):
    """Org-level role assignment: a user holds a role within an organization.

    Project-level role assignment uses the existing ``project_membership.role_id``
    FK column (added in SP6).  Resolution order (SP8): project role overrides
    inherited org role (not a union).

    The unique constraint ensures one org role per user per organization.
    """

    __tablename__ = "organization_member"

    organization_id = Column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        GUID(),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id = Column(
        GUID(),
        ForeignKey("role.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_member_org_user"),
    )

    # Relationships
    role = relationship("Role", back_populates="organization_members")

    def __repr__(self) -> str:
        return (
            f"<OrganizationMember org={self.organization_id} "
            f"user={self.user_id} role={self.role_id}>"
        )


__all__ = [
    "BUILT_IN_ROLE_DESCRIPTIONS",
    "BUILT_IN_ROLE_LEVELS",
    "BUILT_IN_ROLE_NAMES",
    "SCOPE_ORGANIZATION",
    "SCOPE_PROJECT",
    "OrganizationMember",
    "Permission",
    "Role",
    "RolePermission",
    "capability_scope",
    "permissions_for_built_in_role",
]
