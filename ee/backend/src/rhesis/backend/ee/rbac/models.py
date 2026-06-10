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

# Resource types a plain **Member** may act on.
#
# This is a deliberate ALLOWLIST, intentionally narrower than "everything that
# :func:`capability_scope` classifies as project-scoped".  In particular the
# ``project`` entity itself is *excluded* so a Member cannot read/update project
# settings (those require an org Owner / project Admin), while ``project_member``
# is included only so the ``manage`` action can be explicitly withheld (``manage``
# is not in ``member_actions``).
#
# Consequence to keep in mind when adding a new project resource: it will be
# project-scoped per :func:`capability_scope` automatically, but a Member will
# NOT receive its permissions until the resource is added here.  This is
# fail-closed by design (Members gain new capabilities only deliberately).  The
# invariant ``_PROJECT_SCOPED_RESOURCES`` ⊆ {capability_scope == project} is
# asserted in the SP7 tests.
_PROJECT_SCOPED_RESOURCES: frozenset[str] = frozenset(
    {
        "test_set",
        "test",
        "test_configuration",
        "test_run",
        "test_result",
        "experiment",
        "endpoint",
        "metric",
        "model",
        "comment",
        "task",
        "file",
        "project_member",
    }
)

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


def permissions_for_built_in_role(role_name: str, capabilities: list[str]) -> set[str]:
    """Compute the permission set for a built-in role from the capability catalog.

    Called by :func:`~rhesis.backend.ee.rbac.sync.sync_rbac_catalog` to
    recompute built-in role assignments on every startup.

    Rules (locked in plan §2.2):
    - **Owner**  (level 100): all permissions.
    - **Admin**  (level 80): all except EE-only management (role:manage,
      role:read, sso:manage, api_clients:manage).
    - **Member** (level 60): project-scoped :read/:create/:update/:delete plus
      special project actions (:execute, :generate, :import, :react).
    - **Viewer** (level 40): all :read capabilities + recycle:view.
    - **None**   (level 0): no permissions.

    Any name not in the built-in set returns an empty set (fail-closed).
    """
    cap_set = set(capabilities)

    match role_name:
        case "Owner":
            return cap_set
        case "Admin":
            excluded = {"role:manage", "role:read", "sso:manage", "api_clients:manage"}
            return cap_set - excluded
        case "Member":
            member_actions = {
                "read", "create", "update", "delete",
                "execute", "generate", "import", "react",
            }
            return {
                c for c in cap_set
                if c.split(":")[0] in _PROJECT_SCOPED_RESOURCES
                and c.split(":")[-1] in member_actions
            }
        case "Viewer":
            result = {c for c in cap_set if c.endswith(":read")}
            if "recycle:view" in cap_set:
                result.add("recycle:view")
            return result
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

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

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
        UniqueConstraint(
            "organization_id", "user_id", name="uq_organization_member_org_user"
        ),
    )

    # Relationships
    role = relationship("Role", back_populates="organization_members")

    def __repr__(self) -> str:
        return (
            f"<OrganizationMember org={self.organization_id} "
            f"user={self.user_id} role={self.role_id}>"
        )


__all__ = [
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
