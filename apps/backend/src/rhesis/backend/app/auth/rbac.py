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
        _authz=Depends(require_permission(Permission.TestSet.DELETE)),
        ...
    ): ...

    # Or call authorize() directly from service code:
    if not authorize(principal, Permission.Organization.UPDATE, project_id=None, db=db):
        raise HTTPException(403, "Permission denied: organization:update")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.auth.principal import Principal, resolve_principal
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_db_session
from rhesis.backend.app.services.permission_cache import get_permission_cache

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
        permission: "str | Permission",
        *,
        project_id: Optional[UUID],
        db: Session,
    ) -> bool:
        """Return ``True`` iff *principal* holds *permission* in *project_id*.

        Args:
            principal: Resolved caller identity.
            permission: Capability string or :class:`Permission` member,
                e.g. ``Permission.TestSet.READ``.
            project_id: Project scope for project-scoped permissions; ``None``
                for org-scoped permissions (``organization:update``, etc.).
            db: Active tenant-scoped SQLAlchemy session.
        """
        return False


# Capabilities that require org ownership even when no project scope is present.
# Any other capability is accessible to any authenticated org member when
# ``project_id`` is ``None`` (the ORM scope already limits rows to the caller's
# org via ``organization_id`` filtering, so no extra gate is needed).
# EE overrides the whole provider; this set only drives community-tier decisions.
#
# ProjectMember.MANAGE is included here so that managing project membership
# (add/remove/list members) requires org ownership in the community tier.  When
# a project IS in the ambient scope the DefaultAuthorizationProvider would
# normally allow any project member — but membership management is sensitive
# enough that we restrict it to org owners (and, in EE Phase 2, project admins
# via role_id).  This matches the plan §1.5 "org Owner/project admin" ceiling.
_OWNER_ONLY_CAPABILITIES: frozenset[str] = frozenset(
    {
        str(Permission.Organization.UPDATE),
        str(Permission.Member.MANAGE),
        str(Permission.ProjectMember.MANAGE),
        str(Permission.Role.MANAGE),
        str(Permission.Role.READ),
        str(Permission.SSO.MANAGE),
        str(Permission.ApiClients.MANAGE),
        str(Permission.Recycle.RESTORE),
        str(Permission.Recycle.PURGE),
    }
)


class DefaultAuthorizationProvider(AuthorizationProvider):
    """Community-tier provider.

    Decision tree:
    1. ``principal.organization_id is None`` → deny (no org context).
    2. Caller is the org owner → allow (any permission, any scope).
    3. ``project_id`` given + caller has a ``ProjectMembership`` row → allow.
    4. ``project_id`` given + no membership row → deny.
    5. ``project_id`` is ``None`` + permission in ``_OWNER_ONLY_CAPABILITIES`` → deny
       (admin actions reserved for the org owner).
    6. ``project_id`` is ``None`` + permission NOT in ``_OWNER_ONLY_CAPABILITIES`` → allow
       (any org member may perform standard CRUD; the ORM scope limits rows to their org).
    """

    def is_authorized(
        self,
        principal: Principal,
        permission: str,
        *,
        project_id: Optional[UUID],
        db: Session,
    ) -> bool:
        from rhesis.backend.app.models.organization import Organization
        from rhesis.backend.app.models.project_membership import ProjectMembership

        if principal.organization_id is None:
            logger.debug("authorize: deny — no organization on principal %s", principal.user_id)
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
            logger.debug("authorize: deny — not a member of project %s", project_id)
            return False

        # 3. Org-scoped request (no project context).
        #    Owner-only capabilities (org admin, SSO, API clients, etc.) → deny.
        #    All other capabilities → allow (ORM scope filters to the caller's org).
        if str(permission) in _OWNER_ONLY_CAPABILITIES:
            logger.debug(
                "authorize: deny — owner-only capability '%s', principal %s is not owner of org %s",
                permission,
                principal.user_id,
                principal.organization_id,
            )
            return False

        logger.debug(
            "authorize: allow — org member %s for non-owner capability '%s'",
            principal.user_id,
            permission,
        )
        return True


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
    permission: "str | Permission",
    *,
    project_id: Optional[UUID],
    db: Session,
) -> bool:
    """Evaluate whether *principal* holds *permission* in *project_id*.

    This is **the single authorization decision point** for the entire
    platform.  Do not add scattered ownership or role checks elsewhere; direct
    all authorization logic here (or into the active provider).

    Results are cached in Redis DB 5 (plan §1.6) with a 45 s TTL.  The cache
    is keyed by ``(user_id, org_id, project_id, permission)`` — guaranteeing
    no cross-org pollution.  On Redis unavailability the in-process fallback
    handles caching transparently.  Cache entries are busted by
    ``PermissionCache.bust_user`` after membership/role writes.

    Args:
        principal: Resolved caller identity (use :func:`resolve_principal`).
        permission: :class:`Permission` member or raw ``resource:action``
            string, e.g. ``Permission.TestSet.READ`` / ``"test_set:read"``.
        project_id: Target project for project-scoped permissions; ``None`` for
            org-scoped permissions such as ``project:create``.
        db: Active SQLAlchemy session (tenant-scoped from the HTTP request).

    Returns:
        ``True`` if the action is permitted, ``False`` otherwise.  Fail-closed:
        any exception in the provider returns ``False`` and logs the error.
    """
    perm_str = str(permission)

    # Cache is keyed on org context; skip entirely when the org is absent
    # (those are always denies — no value in caching them).
    _cache = get_permission_cache() if principal.organization_id is not None else None

    # --- Cache lookup ---
    if _cache is not None:
        cached = _cache.get(
            user_id=principal.user_id,
            org_id=principal.organization_id,
            project_id=project_id,
            permission=perm_str,
        )
        if cached is not None:
            logger.debug(
                "authorize: cache hit for principal %s permission '%s' → %s",
                principal.user_id,
                perm_str,
                cached,
            )
            return cached

    # --- Call the active provider ---
    try:
        result = _AuthorizationRegistry.get_authorization_provider().is_authorized(
            principal, permission, project_id=project_id, db=db
        )
    except Exception:
        logger.exception(
            "authorize: unexpected error evaluating '%s' for principal %s — denying",
            permission,
            principal.user_id,
        )
        return False

    # --- Store result in cache (exceptions are non-fatal) ---
    if _cache is not None:
        try:
            _cache.set(
                user_id=principal.user_id,
                org_id=principal.organization_id,
                project_id=project_id,
                permission=perm_str,
                result=result,
            )
        except Exception as exc:
            logger.warning("authorize: cache set failed (non-fatal): %s", exc)

    return result


# ---------------------------------------------------------------------------
# FastAPI dependency factory — for explicit per-route use (before SP4 PEP)
# ---------------------------------------------------------------------------


def require_permission(capability: "str | Permission"):
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
        request: Request,
        db: Session = Depends(get_tenant_db_session),
        current_user=Depends(require_current_user_or_token),
    ) -> None:
        # SP9: forward token scopes from request state (set by
        # get_authenticated_user_with_context for rh-* API tokens).
        token_scopes: Optional[frozenset[str]] = getattr(request.state, "api_token_scopes", None)
        token_project_id_str: Optional[str] = getattr(request.state, "api_token_project_id", None)
        tok_project_id: Optional[UUID] = None
        if token_project_id_str is not None:
            try:
                tok_project_id = UUID(token_project_id_str)
            except (ValueError, AttributeError):
                pass

        principal = resolve_principal(
            current_user,
            scopes=token_scopes,
            token_project_id=tok_project_id,
            kind="token" if token_scopes is not None or tok_project_id is not None else "session",
        )

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
    "Permission",
    "authorize",
    "get_authorization_provider",
    "require_permission",
    "set_authorization_provider",
]
