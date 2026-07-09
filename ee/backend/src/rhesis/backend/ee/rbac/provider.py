"""EE PermissionAuthorizationProvider — SP8.

Replaces :class:`~rhesis.backend.app.auth.rbac.DefaultAuthorizationProvider`
for orgs with the RBAC feature enabled.  Installed via
:func:`~rhesis.backend.app.auth.rbac.set_authorization_provider` in
:func:`~rhesis.backend.ee.__init__.bootstrap`.

Resolution order:
1. If RBAC is not available for the org → delegate to the community provider.
2. No org role at all (org-scoped checks) → deny; org-scoped permissions
   require an org role. (For project-scoped checks, see step 5 — a pure
   project member with no org role is still governed by their explicit
   project role.)
3. Org Admin or Owner (level >= 80): implicit access to all projects. Their
   org role applies as the effective project role. They do not need to be
   individually enrolled in every project.
4. Org Member or Viewer (level < 80): explicit project enrollment is
   required. If a ``project_membership`` row exists (even with
   ``role_id = NULL``), their org role applies to that project. If no
   membership row exists, access is denied for that project.
5. If the user also has an explicit ``project_membership.role_id`` for this
   project, it is compared against the org role (when one exists) and the
   **higher-level** role wins — an explicit project role can elevate access
   above the org role, but can never restrict it below what the org role
   already grants. With no org role at all, the explicit project role is
   the whole answer.

The rationale for the Admin/Owner implicit-access rule mirrors tools like
GitHub, Linear, and Notion: org-level administrators see and can manage all
workspaces/projects without being individually added to each one.  Contributors
(Member/Viewer) are scoped to projects they have been explicitly invited to.

"Higher role wins, never restricts" (step 5) mirrors GitLab's inherited-membership
rule and GCP IAM's resource-hierarchy inheritance: a narrower scope (project) can
only add to what a broader scope (organization) already grants. An org Owner
assigned a lower explicit role on one project still keeps Owner-level access to
that project; an org Member assigned Owner on one project gets elevated access
to that project only.

The ``Role`` model has ``organization_id`` which triggers the ORM
``auto_filter`` event.  Built-in roles (``organization_id IS NULL``) would be
hidden by the filter because ``NULL != <any UUID>``.  All role lookups here use
:func:`~rhesis.backend.app.scope.bypass_tenant_filter` to suppress that filter.
The DB-level RLS policy on ``role`` already permits NULL-org rows (SP7
migration), so this bypass only affects the ORM layer — not the DB security
boundary.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from rhesis.backend.app.auth.principal import Principal

logger = logging.getLogger(__name__)


class PermissionAuthorizationProvider:
    """EE authorization provider: resolves roles and checks the permission table.

    Installed at EE bootstrap; replaces
    :class:`~rhesis.backend.app.auth.rbac.DefaultAuthorizationProvider` for the
    lifetime of the process.  The community provider remains reachable as the
    fallback when RBAC is not licensed for a specific org.
    """

    def __init__(self) -> None:
        # Lazy import keeps the community provider available as a fallback
        # without circular-import risk at module load time.
        from rhesis.backend.app.auth.rbac import DefaultAuthorizationProvider

        self._fallback = DefaultAuthorizationProvider()

    def is_authorized(
        self,
        principal: "Principal",
        permission: "str",
        *,
        project_id: Optional[UUID],
        db: "Session",
    ) -> bool:
        """Return ``True`` iff *principal* holds *permission* in *project_id*.

        Delegates to the community fallback when RBAC is not available for the
        org.  Fail-closed on any missing context.
        """
        if principal.organization_id is None:
            return False

        if not self._rbac_available(principal, db):
            return self._fallback.is_authorized(principal, permission, project_id=project_id, db=db)

        perm_str = str(permission)
        effective_role = self._resolve_role(principal, project_id, db)

        if effective_role is None:
            logger.debug(
                "authorize(ee): deny — no role resolved for principal %s (project=%s)",
                principal.user_id,
                project_id,
            )
            return False

        role_allows = self._role_has_permission(effective_role, perm_str, db)
        if not role_allows:
            return False

        # SP9: token scope intersection.  If the authenticating token carries an
        # explicit scope set, the permission must also appear there — the token
        # cannot exceed the owner's access and the owner cannot exceed the token's.
        # This auto-narrows on owner downgrade: if the role check above failed,
        # we already returned False; stale wide scopes never help.
        if principal.scopes is not None and perm_str not in principal.scopes:
            return False

        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rbac_available(self, principal: "Principal", db: "Session") -> bool:
        """Return True when RBAC is licensed and registered for the principal's org."""
        from rhesis.backend.app.features import FeatureName, FeatureRegistry
        from rhesis.backend.app.models.organization import Organization
        from rhesis.backend.app.scope import bypass_tenant_filter

        with bypass_tenant_filter():
            org = db.query(Organization).filter_by(id=principal.organization_id).first()
        if org is None:
            return False
        return FeatureRegistry.is_available(FeatureName.RBAC, org)

    #: Minimum role level that grants implicit access to all projects without
    #: requiring an explicit project_membership row.  Corresponds to Admin (80).
    _IMPLICIT_PROJECT_ACCESS_LEVEL = 80

    def _resolve_role(self, principal: "Principal", project_id: Optional[UUID], db: "Session"):
        """Return the effective :class:`~rhesis.backend.ee.rbac.models.Role` or None.

        When a project context is present, access is gated by org role level
        and enrollment first, then the org role and any explicit project role
        are compared and the **higher-level** one is returned:

        1. No org role at all — the explicit project role (if any) governs
           directly; there is no org-level floor to compare it against. This
           is the pure project-member case (e.g. a user with no
           ``organization_member`` row at all).
        2. Org role level >= Admin (80): implicit access to every project.
        3. Org role level < Admin: explicit enrollment required — a
           ``project_membership`` row (even with ``role_id = NULL``) must
           exist, or access is denied outright.
        4. If an explicit ``project_membership.role_id`` is also set, it is
           compared against the org role by ``level``; the higher one wins.
           A project role can elevate access above the org role but can never
           restrict it below what the org role already grants (see module
           docstring — "higher role wins, never restricts").
        """
        if project_id is None:
            return self._get_org_role(principal, db)

        org_role = self._get_org_role(principal, db)

        membership = self._get_project_membership(principal, project_id, db)
        explicit_role = None
        if membership is not None and membership.role_id is not None:
            explicit_role = self._load_role(membership.role_id, db)

        if org_role is None:
            # No org-level floor to enforce — the explicit project role (if
            # any) is the whole answer. If the membership row exists but
            # role_id is NULL (e.g. its custom role was deleted — see
            # delete_role's docstring in router.py), this deliberately
            # resolves to None (deny) rather than falling back to some
            # default project role: with no org role to compare against,
            # there is no floor to fall back to, and granting access here
            # would let a role deletion silently re-grant standard access to
            # holders an admin may be deliberately locking out. Community
            # mode's DefaultAuthorizationProvider treats a bare membership
            # row as implicit standard access with no equivalent "delete the
            # role" trigger, so the two tiers are not directly comparable.
            return explicit_role

        if org_role.level >= self._IMPLICIT_PROJECT_ACCESS_LEVEL:
            # Admin / Owner: implicit access to all projects; an explicit
            # project role can only elevate further.
            if explicit_role is not None and explicit_role.level > org_role.level:
                return explicit_role
            return org_role

        # Member / Viewer: explicit enrollment required to access the project.
        if explicit_role is not None:
            return explicit_role if explicit_role.level > org_role.level else org_role
        if membership is not None:
            return org_role

        return None

    def _get_project_membership(self, principal: "Principal", project_id: UUID, db: "Session"):
        """Return the raw ``ProjectMembership`` row for this principal, or None."""
        from rhesis.backend.app.models.project_membership import ProjectMembership

        return (
            db.query(ProjectMembership)
            .filter_by(
                project_id=project_id,
                user_id=principal.user_id,
                organization_id=principal.organization_id,
            )
            .first()
        )

    def _load_role(self, role_id, db: "Session"):
        """Return the :class:`~rhesis.backend.ee.rbac.models.Role` for *role_id*."""
        from rhesis.backend.app.scope import bypass_tenant_filter
        from rhesis.backend.ee.rbac.models import Role

        with bypass_tenant_filter():
            return db.query(Role).filter_by(id=role_id).first()

    def _get_org_role(self, principal: "Principal", db: "Session"):
        """Return the org-level role for the principal, or None."""
        from rhesis.backend.ee.rbac.models import OrganizationMember

        member = (
            db.query(OrganizationMember)
            .filter_by(
                organization_id=principal.organization_id,
                user_id=principal.user_id,
            )
            .first()
        )
        if member is None or member.role_id is None:
            return None

        return self._load_role(member.role_id, db)

    def _role_has_permission(self, role, perm_str: str, db: "Session") -> bool:
        """Return True when *role* carries *perm_str*.

        Built-in roles compute their permission set from code via
        :func:`~rhesis.backend.ee.rbac.models.permissions_for_built_in_role` —
        no ``role_permission`` rows are read or required for them.  Custom roles
        (``is_built_in=False``) resolve via the ``role_permission`` join as
        before.  This eliminates the need to keep ``role_permission`` rows in
        sync for built-in roles.
        """
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.ee.rbac.models import (
            Permission,
            RolePermission,
            permissions_for_built_in_role,
        )

        if role.is_built_in:
            return perm_str in permissions_for_built_in_role(role.name, get_all_capabilities())

        # Custom role: resolve via role_permission join.
        rp = (
            db.query(RolePermission)
            .join(Permission, RolePermission.permission_id == Permission.id)
            .filter(
                RolePermission.role_id == role.id,
                Permission.name == perm_str,
                Permission.is_retired.is_(False),
            )
            .first()
        )
        return rp is not None

    def resolve_effective_role(
        self, principal: "Principal", project_id: Optional[UUID], db: "Session"
    ):
        """Return the effective :class:`~rhesis.backend.ee.rbac.models.Role` or None.

        Returns ``None`` when RBAC is off for the org, when the principal has no
        org context, or when no membership row exists at either tier.  Used by the
        router to resolve the actor's level and permissions in a single DB pass.
        """
        if principal.organization_id is None:
            return None
        if not self._rbac_available(principal, db):
            return None
        return self._resolve_role(principal, project_id, db)

    def get_effective_permissions(
        self, principal: "Principal", project_id: Optional[UUID], db: "Session"
    ) -> set[str]:
        """Return the full set of active permission names for the principal.

        Used by ``GET /me/permissions`` and the privilege-escalation guard to
        inspect what the actor actually holds before a role create/assign.
        Returns an empty set when RBAC is off or no role is found.

        Built-in roles compute their permission set from code; custom roles
        query ``role_permission``.  See :meth:`_role_has_permission`.
        """
        if not self._rbac_available(principal, db):
            return set()

        role = self._resolve_role(principal, project_id, db)
        if role is None:
            return set()

        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.ee.rbac.models import (
            Permission,
            RolePermission,
            permissions_for_built_in_role,
        )

        if role.is_built_in:
            return permissions_for_built_in_role(role.name, get_all_capabilities())

        rows = (
            db.query(Permission.name)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .filter(
                RolePermission.role_id == role.id,
                Permission.is_retired.is_(False),
            )
            .all()
        )
        return {row[0] for row in rows}


__all__ = ["PermissionAuthorizationProvider"]
