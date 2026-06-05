"""Authorization PDP — Policy Decision Point.

Every allow/deny decision in the platform flows through :func:`authorize`.
Nothing else in the codebase should contain scattered ownership or role checks;
those belong here (or in a custom :class:`AuthorizationProvider`).

Community tier — :class:`DefaultAuthorizationProvider`:
  - Org owner (``organization.owner_id == principal.user_id``) → allow any
    permission, project-scoped or org-scoped.
  - Project member (``project_membership`` row exists for the given
    ``project_id``) → allow project-scoped permissions.
  - ``role_id`` on ``ProjectMembership`` is intentionally ignored in community
    mode; it is honored by ``PermissionAuthorizationProvider`` in EE Phase 2
    (SP8).
  - Org-scoped permissions (``project_id=None``) require org ownership.
  - Missing organization context → fail-closed (deny).

EE tier — installed at bootstrap via :func:`set_authorization_provider`:
  ``PermissionAuthorizationProvider`` resolves effective roles, checks the
  ``permission`` DB table, and applies custom role overrides (SP8).

Usage in route handlers (before the PEP backstop wires it automatically, SP4)::

    from rhesis.backend.app.auth.rbac import authorize, require_permission

    # Explicit per-route check:
    @router.delete("/{id}")
    def delete_item(
        id: UUID,
        _authz=Depends(require_permission("test_set:delete")),
        ...
    ): ...

    # Or call authorize() directly from service code:
    if not authorize(principal, "organization:update", project_id=None, db=db):
        raise HTTPException(403, "Permission denied: organization:update")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.principal import Principal, resolve_principal
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_db_session

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider protocol + community implementation
# ---------------------------------------------------------------------------


class AuthorizationProvider:
    """Base authorization provider — subclasses override :meth:`is_authorized`.

    The base class never grants access; it is fail-closed by default.
    Install a replacement via :func:`set_authorization_provider`.
    """

    def is_authorized(
        self,
        principal: Principal,
        permission: str,
        *,
        project_id: Optional[UUID],
        db: Session,
    ) -> bool:
        """Return ``True`` iff *principal* holds *permission* in *project_id*.

        Args:
            principal: Resolved caller identity.
            permission: Capability string, e.g. ``"test_set:read"``.
            project_id: Project scope for project-scoped permissions; ``None``
                for org-scoped permissions (``organization:update``, etc.).
            db: Active tenant-scoped SQLAlchemy session.
        """
        return False


class DefaultAuthorizationProvider(AuthorizationProvider):
    """Community-tier provider.

    Decision tree:
    1. ``principal.organization_id is None`` → deny (no org context).
    2. Caller is the org owner → allow (any permission, any scope).
    3. ``project_id`` given + caller has a ``ProjectMembership`` row → allow.
    4. ``project_id`` is ``None`` (org-scoped permission) → deny
       (org owner already handled above; no non-owner org actions in community).
    5. Caller has no membership in the project → deny.
    """

    def is_authorized(
        self,
        principal: Principal,
        permission: str,  # noqa: ARG002 — EE uses this; community checks membership only
        *,
        project_id: Optional[UUID],
        db: Session,
    ) -> bool:
        from rhesis.backend.app.models.organization import Organization
        from rhesis.backend.app.models.project_membership import ProjectMembership

        if principal.organization_id is None:
            logger.debug(
                "authorize: deny — no organization on principal %s", principal.user_id
            )
            return False

        # 1. Org owner bypass — allowed for every permission.
        org = (
            db.query(Organization)
            .filter_by(id=principal.organization_id, owner_id=principal.user_id)
            .first()
        )
        if org is not None:
            logger.debug(
                "authorize: allow — org owner %s for org %s",
                principal.user_id,
                principal.organization_id,
            )
            return True

        # 2. Project-scoped permission: require project membership.
        if project_id is not None:
            membership = (
                db.query(ProjectMembership)
                .filter_by(
                    project_id=project_id,
                    user_id=principal.user_id,
                    organization_id=principal.organization_id,
                )
                .first()
            )
            if membership is not None:
                logger.debug(
                    "authorize: allow — project member %s in project %s",
                    principal.user_id,
                    project_id,
                )
                return True
            logger.debug(
                "authorize: deny — not a member of project %s", project_id
            )
            return False

        # 3. Org-scoped permission, caller is not the owner → deny.
        logger.debug(
            "authorize: deny — org-scoped permission, principal %s is not owner of org %s",
            principal.user_id,
            principal.organization_id,
        )
        return False


# ---------------------------------------------------------------------------
# Registry — mirrors FeatureRegistry; one active provider per process
# ---------------------------------------------------------------------------


class _AuthorizationRegistry:
    """Singleton registry for the active :class:`AuthorizationProvider`.

    Community mode installs :class:`DefaultAuthorizationProvider` by default.
    EE bootstrap (SP8) replaces it via :func:`set_authorization_provider` once
    at startup.
    """

    _provider: AuthorizationProvider = DefaultAuthorizationProvider()

    @classmethod
    def set_authorization_provider(cls, provider: AuthorizationProvider) -> None:
        """Install a new provider. Call once at bootstrap; not thread-safe during the swap."""
        cls._provider = provider

    @classmethod
    def get_authorization_provider(cls) -> AuthorizationProvider:
        """Return the currently active provider."""
        return cls._provider

    @classmethod
    def reset(cls) -> None:
        """Reinstall the default provider. For tests only."""
        cls._provider = DefaultAuthorizationProvider()


# Module-level convenience wrappers (preferred call sites).


def set_authorization_provider(provider: AuthorizationProvider) -> None:
    """Install the active authorization provider (called by EE bootstrap)."""
    _AuthorizationRegistry.set_authorization_provider(provider)


def get_authorization_provider() -> AuthorizationProvider:
    """Return the active authorization provider."""
    return _AuthorizationRegistry.get_authorization_provider()


# ---------------------------------------------------------------------------
# PDP — the single decision point
# ---------------------------------------------------------------------------


def authorize(
    principal: Principal,
    permission: str,
    *,
    project_id: Optional[UUID],
    db: Session,
) -> bool:
    """Evaluate whether *principal* holds *permission* in *project_id*.

    This is **the single authorization decision point** for the entire
    platform.  Do not add scattered ownership or role checks elsewhere; direct
    all authorization logic here (or into the active provider).

    Args:
        principal: Resolved caller identity (use :func:`resolve_principal`).
        permission: Capability string in ``resource:action`` form, e.g.
            ``"test_set:read"`` or ``"organization:update"``.
        project_id: Target project for project-scoped permissions; ``None`` for
            org-scoped permissions such as ``project:create``.
        db: Active SQLAlchemy session (tenant-scoped from the HTTP request).

    Returns:
        ``True`` if the action is permitted, ``False`` otherwise.  Fail-closed:
        any exception in the provider returns ``False`` and logs the error.
    """
    try:
        return _AuthorizationRegistry.get_authorization_provider().is_authorized(
            principal, permission, project_id=project_id, db=db
        )
    except Exception:
        logger.exception(
            "authorize: unexpected error evaluating '%s' for principal %s — denying",
            permission,
            principal.user_id,
        )
        return False


# ---------------------------------------------------------------------------
# FastAPI dependency factory — for explicit per-route use (before SP4 PEP)
# ---------------------------------------------------------------------------


def require_permission(capability: str):
    """FastAPI dependency factory that enforces a single capability check.

    Returns a parameterless dependency that:
    1. Resolves the ``Principal`` from the authenticated user.
    2. Reads ``project_id`` from the ambient request scope
       (``db.info['_scope']``, written by ``get_db_with_tenant_variables``).
    3. Calls :func:`authorize`; raises ``HTTP 403`` on denial.

    Usage (direct annotation before the PEP wires it automatically in SP4)::

        @router.delete("/{id}")
        def delete_item(
            id: UUID,
            _authz=Depends(require_permission("test_set:delete")),
            db: Session = Depends(get_tenant_db_session),
            current_user=Depends(require_current_user_or_token),
        ):
            ...

    The SP4 PEP backstop (``apply_authz_backstop``) injects this dependency on
    every CRUD route automatically so individual handlers don't need it.
    """

    def _dependency(
        db: Session = Depends(get_tenant_db_session),
        current_user=Depends(require_current_user_or_token),
    ) -> None:
        principal = resolve_principal(current_user)

        # Read project_id from the ambient scope written by get_db_with_tenant_variables.
        scope = db.info.get("_scope")
        project_id: Optional[UUID] = getattr(scope, "project_id", None)
        if project_id is not None and not isinstance(project_id, UUID):
            try:
                project_id = UUID(str(project_id))
            except (ValueError, AttributeError):
                project_id = None

        if not authorize(principal, capability, project_id=project_id, db=db):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {capability}",
            )

    return _dependency


__all__ = [
    "AuthorizationProvider",
    "DefaultAuthorizationProvider",
    "authorize",
    "get_authorization_provider",
    "require_permission",
    "set_authorization_provider",
]
