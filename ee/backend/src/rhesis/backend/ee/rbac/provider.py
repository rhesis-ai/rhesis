"""EE PermissionAuthorizationProvider — SP8.

Replaces :class:`~rhesis.backend.app.auth.rbac.DefaultAuthorizationProvider`
for orgs with the RBAC feature enabled.  Installed via
:func:`~rhesis.backend.app.auth.rbac.set_authorization_provider` in
:func:`~rhesis.backend.ee.__init__.bootstrap`.

Resolution order (locked, plan §2.3):
1. If RBAC is not available for the org → delegate to the community provider.
2. If a ``project_id`` is given and the user has a ``project_membership`` row
   with a non-NULL ``role_id`` → the project role governs (overrides org role,
   not a union).
3. Otherwise the user's ``organization_member.role_id`` governs.
4. No membership row at either tier → deny.

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

        result = self._role_has_permission(effective_role, perm_str, db)
        logger.debug(
            "authorize(ee): principal %s role %r permission %r → %s",
            principal.user_id,
            effective_role.name,
            perm_str,
            result,
        )
        return result

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

    def _resolve_role(self, principal: "Principal", project_id: Optional[UUID], db: "Session"):
        """Return the effective :class:`~rhesis.backend.ee.rbac.models.Role` or None.

        Project role beats org role when both are present (override, not union).
        """
        if project_id is not None:
            role = self._get_project_role(principal, project_id, db)
            if role is not None:
                return role

        return self._get_org_role(principal, db)

    def _get_project_role(self, principal: "Principal", project_id: UUID, db: "Session"):
        """Return the project-scoped role for the principal, or None."""
        from rhesis.backend.app.models.project_membership import ProjectMembership
        from rhesis.backend.app.scope import bypass_tenant_filter
        from rhesis.backend.ee.rbac.models import Role

        membership = (
            db.query(ProjectMembership)
            .filter_by(
                project_id=project_id,
                user_id=principal.user_id,
                organization_id=principal.organization_id,
            )
            .first()
        )
        if membership is None or membership.role_id is None:
            return None

        with bypass_tenant_filter():
            return db.query(Role).filter_by(id=membership.role_id).first()

    def _get_org_role(self, principal: "Principal", db: "Session"):
        """Return the org-level role for the principal, or None."""
        from rhesis.backend.app.scope import bypass_tenant_filter
        from rhesis.backend.ee.rbac.models import OrganizationMember, Role

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

        with bypass_tenant_filter():
            return db.query(Role).filter_by(id=member.role_id).first()

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
