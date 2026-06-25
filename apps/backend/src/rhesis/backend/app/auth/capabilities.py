"""Capability map — derives ``resource:action`` names from registered routes.

**How it works**

Every :class:`~rhesis.backend.app.routers.base.RhesisRouter` stamps
``openapi_extra["x-rhesis-resource"]`` on each route it owns.
:func:`get_capability_for_route` reads that stamp and combines it with the
HTTP verb (``GET→read``, ``POST→create``, …) to produce a capability string.
Non-CRUD routes carry an explicit ``openapi_extra["x-rhesis-capability"]``
override via the :func:`capability` helper.

**Lifecycle**

:func:`register_capabilities` is called once from ``main.py`` after all
routers (core + EE) are registered.  It walks ``app.router.routes``, builds
the ``capability → [paths]`` map, and caches the sorted capability list.
:func:`get_all_capabilities` returns that cached list.  Any call before
registration logs a warning and returns ``[]``.

**Phase 2 (SP7)**

``get_all_capabilities()`` will read from the seeded ``permission`` DB table
so new capabilities appear without a re-deploy.  :func:`build_capability_map`
becomes the CI drift guard, failing the build when a route maps to a capability
not in the catalog.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission catalog — canonical ``resource:action`` constants
# ---------------------------------------------------------------------------


class _PermissionEnum(str, Enum):
    """Base for all Permission sub-enums.

    Inheriting from ``str`` makes every member a real string — no ``.value``
    access needed when passing to :func:`authorize`, :func:`require_permission`,
    or :func:`capability`.

    ``__str__`` is overridden to return the *value* (``"member:manage"``) rather
    than Python's default Enum representation (``"Member.MANAGE"``), so members
    behave like plain strings in f-strings, ``str()``, and ``re.match``.
    """

    def __str__(self) -> str:
        return self.value


class Permission:
    """Namespace of ``resource:action`` capability constants, grouped by resource.

    Each nested class is a ``str`` enum so members can be used anywhere a plain
    string is accepted::

        authorize(principal, Permission.Member.MANAGE, project_id=None, db=db)
        @router.post("/restore", **capability(Permission.Recycle.RESTORE))
        require_permission(Permission.TestSet.DELETE)

    **Catalogue structure** (mirrors master design doc §4 permission catalog):

    - Test authoring (project-scoped): :class:`TestSet`, :class:`Test`
    - Test execution & results (project-scoped): :class:`TestRun`,
      :class:`TestResult`, :class:`TestConfiguration`, :class:`Experiment`
    - Endpoints & connectors (project-scoped): :class:`Endpoint`
    - Metrics & models (project-scoped): :class:`Metric`, :class:`Model`
    - Collaboration (project-scoped): :class:`Comment`, :class:`Task`
    - Files (project/org): :class:`File`
    - Project administration (project-scoped): :class:`Project`,
      :class:`ProjectMember`
    - Organization administration (org-scoped): :class:`Organization`,
      :class:`Member`, :class:`Role`, :class:`Token`
    - Recycle bin (org-scoped): :class:`Recycle`
    - EE gates (org-scoped, guarded by ``FeatureName.RBAC``): :class:`SSO`,
      :class:`ApiClients`
    """

    # --- Test authoring (project-scoped) ------------------------------------

    class TestSet(_PermissionEnum):
        READ = "test_set:read"
        CREATE = "test_set:create"
        UPDATE = "test_set:update"
        DELETE = "test_set:delete"
        GENERATE = "test_set:generate"
        EXECUTE = "test_set:execute"

    class Test(_PermissionEnum):
        READ = "test:read"
        CREATE = "test:create"
        UPDATE = "test:update"
        DELETE = "test:delete"

    # --- Test execution & results (project-scoped) --------------------------

    class TestConfiguration(_PermissionEnum):
        READ = "test_configuration:read"
        CREATE = "test_configuration:create"
        UPDATE = "test_configuration:update"
        DELETE = "test_configuration:delete"

    class TestRun(_PermissionEnum):
        READ = "test_run:read"
        CREATE = "test_run:create"
        UPDATE = "test_run:update"
        DELETE = "test_run:delete"
        EXECUTE = "test_run:execute"

    class TestResult(_PermissionEnum):
        READ = "test_result:read"
        UPDATE = "test_result:update"

    class Experiment(_PermissionEnum):
        READ = "experiment:read"
        CREATE = "experiment:create"
        UPDATE = "experiment:update"
        DELETE = "experiment:delete"

    # --- Endpoints & connectors (project-scoped) ----------------------------

    class Endpoint(_PermissionEnum):
        READ = "endpoint:read"
        CREATE = "endpoint:create"
        UPDATE = "endpoint:update"
        DELETE = "endpoint:delete"

    # --- Metrics & models (project-scoped) ----------------------------------

    class Metric(_PermissionEnum):
        READ = "metric:read"
        CREATE = "metric:create"
        UPDATE = "metric:update"
        DELETE = "metric:delete"

    class Model(_PermissionEnum):
        READ = "model:read"
        CREATE = "model:create"
        UPDATE = "model:update"
        DELETE = "model:delete"

    # --- Collaboration (project-scoped) -------------------------------------

    class Comment(_PermissionEnum):
        READ = "comment:read"
        CREATE = "comment:create"
        UPDATE = "comment:update"
        DELETE = "comment:delete"
        REACT = "comment:react"
        #: Update a comment the caller created (object-level :own qualifier).
        UPDATE_OWN = "comment:update:own"
        #: Delete a comment the caller created (object-level :own qualifier).
        DELETE_OWN = "comment:delete:own"

    class Task(_PermissionEnum):
        READ = "task:read"
        CREATE = "task:create"
        UPDATE = "task:update"
        DELETE = "task:delete"

    # --- Architect agent (project-scoped, WebSocket-driven) -----------------

    class Architect(_PermissionEnum):
        """Architect agent sessions. Checked in the WebSocket handler, not on a
        route — ``READ`` gates channel subscription, ``CREATE`` gates sending a
        message that enqueues an agent run (SP11)."""

        READ = "architect:read"
        CREATE = "architect:create"

    class Preflight(_PermissionEnum):
        """Ephemeral preflight operation channel (WebSocket, SP11)."""

        CREATE = "preflight:create"

    # --- Files (project/org) ------------------------------------------------

    class File(_PermissionEnum):
        READ = "file:read"
        CREATE = "file:create"
        UPDATE = "file:update"
        DELETE = "file:delete"
        IMPORT = "file:import"

    # --- Project administration (project-scoped) ----------------------------

    class Project(_PermissionEnum):
        READ = "project:read"
        #: Create a new project inside the org (org-scoped action).
        CREATE = "project:create"
        UPDATE = "project:update"

    class ProjectMember(_PermissionEnum):
        #: List/add/remove project members. Owner-only in the community tier
        #: (plan §1.5); EE Phase 2 (SP8) grants it via project-admin roles.
        MANAGE = "project_member:manage"

    # --- Organization administration (org-scoped) ---------------------------

    class Organization(_PermissionEnum):
        READ = "organization:read"
        UPDATE = "organization:update"

    class Member(_PermissionEnum):
        READ = "member:read"
        #: Add a member to the org (route-derived companion of MANAGE).
        CREATE = "member:create"
        #: Remove a member from the org (route-derived companion of MANAGE).
        DELETE = "member:delete"
        #: Invite or remove members from the org.
        MANAGE = "member:manage"
        #: Update a user's own profile (self-service sub-action of MANAGE).
        UPDATE = "member:update"

    class Role(_PermissionEnum):
        """Custom-role CRUD — EE only, guarded by ``FeatureName.RBAC``."""

        READ = "role:read"
        MANAGE = "role:manage"

    class Token(_PermissionEnum):
        MANAGE = "token:manage"

    # --- Recycle bin (org-scoped) -------------------------------------------

    class Recycle(_PermissionEnum):
        VIEW = "recycle:view"
        RESTORE = "recycle:restore"
        PURGE = "recycle:purge"

    # --- EE gates (org-scoped) ----------------------------------------------

    class SSO(_PermissionEnum):
        """SSO configuration — EE only."""

        MANAGE = "sso:manage"

    class ApiClients(_PermissionEnum):
        """M2M API client management — EE only."""

        MANAGE = "api_clients:manage"


# ---------------------------------------------------------------------------
# openapi_extra keys
# ---------------------------------------------------------------------------

# Set by @capability() on individual routes.
_CAPABILITY_KEY = "x-rhesis-capability"

# Set by RhesisRouter.add_api_route() on every route it owns.
_RESOURCE_KEY = "x-rhesis-resource"

# ---------------------------------------------------------------------------
# HTTP method → action
# ---------------------------------------------------------------------------

_METHOD_TO_ACTION: dict[str, str] = {
    "GET": "read",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}

# ---------------------------------------------------------------------------
# Paths that are silently skipped (no "unmapped" warning).
# ---------------------------------------------------------------------------

_DERIVER_SKIP_PATHS: frozenset[str] = frozenset(
    ["/", "/health", "/docs", "/openapi.json", "/redoc"]
)


# ---------------------------------------------------------------------------
# @capability decorator helper
# ---------------------------------------------------------------------------


def capability(name: "str | Permission") -> dict:
    """Return ``openapi_extra`` kwargs marking a route with an explicit capability.

    Unpack into the FastAPI route decorator for non-CRUD routes whose action
    cannot be inferred from the HTTP verb alone.  Prefer :class:`Permission`
    constants over bare strings::

        @router.post("/generate", **capability(Permission.TestSet.GENERATE))
        async def generate_test_set(...):
            ...

    The deriver checks for this key first; it overrides the resource+verb
    convention when both are present.
    """
    return {"openapi_extra": {_CAPABILITY_KEY: str(name)}}


# ---------------------------------------------------------------------------
# Core deriver
# ---------------------------------------------------------------------------


def _action_from_route(route: object) -> Optional[str]:
    methods: set[str] = getattr(route, "methods", None) or set()
    for method in ("DELETE", "PUT", "PATCH", "POST", "GET"):
        if method in methods:
            return _METHOD_TO_ACTION.get(method)
    return None


def get_capability_for_route(route: object) -> Optional[str]:
    """Return the ``resource:action`` capability for *route*, or ``None``.

    Decision order:

    1. Route path is in the skip-list → ``None`` (silently skipped).
    2. ``openapi_extra["x-rhesis-capability"]`` is set → return it directly
       (explicit override from ``@capability()``).
    3. ``openapi_extra["x-rhesis-resource"]`` is set (stamped by
       :class:`~rhesis.backend.app.routers.base.RhesisRouter`) → combine with
       HTTP-verb action.
    4. Neither is set → ``None`` (logged as unmapped by
       :func:`build_capability_map`).
    """
    path: str = getattr(route, "path", "") or ""
    if path in _DERIVER_SKIP_PATHS:
        return None

    extra: dict = getattr(route, "openapi_extra", None) or {}

    # Explicit override wins.
    if _CAPABILITY_KEY in extra:
        return extra[_CAPABILITY_KEY]

    # Convention: resource (from RhesisRouter stamp) + verb action.
    resource: Optional[str] = extra.get(_RESOURCE_KEY)
    if not resource:
        return None

    action = _action_from_route(route)
    if action is None:
        return None

    return f"{resource}:{action}"


def build_capability_map(app: object) -> dict[str, list[str]]:
    """Walk all registered routes and return ``{capability: [path, ...]}``.

    Runs in **report-only mode**: logs warnings for routes with no capability
    mapping but does not raise.  The SP7 drift guard will promote these
    warnings to CI failures.

    Args:
        app: The FastAPI application instance (after all routers are included).

    Returns:
        Mapping from ``"resource:action"`` strings to the list of route paths
        that resolved to that capability.
    """
    from fastapi.routing import APIRoute

    capability_map: dict[str, list[str]] = {}
    unmapped: list[str] = []

    for route in getattr(app, "router", app).routes:
        if not isinstance(route, APIRoute):
            continue
        cap = get_capability_for_route(route)
        if cap is None:
            p: str = getattr(route, "path", "")
            if p not in _DERIVER_SKIP_PATHS:
                methods = sorted(getattr(route, "methods", None) or [])
                unmapped.append(f"{','.join(methods)}: {p}")
            continue
        capability_map.setdefault(cap, []).append(getattr(route, "path", ""))

    if unmapped:
        logger.info(
            "capability deriver: %d route(s) with no capability mapping "
            "(report-only — add resource= to the router or @capability() to the route): %s",
            len(unmapped),
            ", ".join(sorted(unmapped)),
        )

    return capability_map


# ---------------------------------------------------------------------------
# Startup registration + runtime accessor
# ---------------------------------------------------------------------------

_capability_cache: Optional[list[str]] = None


def enumerate_permission_enum() -> set[str]:
    """Return every capability string declared on the :class:`Permission` enum.

    The convention deriver (resource + HTTP verb) only surfaces capabilities
    that are gated *on a route*.  Some capabilities are checked in handler or
    service code instead (e.g. ``member:manage`` in ``PUT /users/{id}``,
    ``role:manage`` in the role router's escalation guard, ``recycle:view``),
    so they never appear in a route's resource×verb mapping.  The ``Permission``
    enum is the authoritative declaration of those, so the full catalog is the
    union of the route-derived set and these enum values.
    """
    values: set[str] = set()
    for member in vars(Permission).values():
        if isinstance(member, type) and issubclass(member, _PermissionEnum):
            values.update(str(m.value) for m in member)
    return values


def register_capabilities(app: object) -> None:
    """Derive and cache the full capability catalog.

    The catalog is the union of:

    1. Route-derived capabilities (resource×verb convention + ``@capability``
       overrides), from :func:`build_capability_map`.
    2. Capabilities declared on the :class:`Permission` enum but checked in
       handler/service code rather than gated on a route (see
       :func:`enumerate_permission_enum`).

    Must be called **once**, from ``main.py``, after all routers (core + EE)
    have been included and *after* :func:`apply_auth_backstop` has run (so EE
    routes are visible).

    Idempotent: re-calling replaces the cache (useful in tests that rebuild
    the app).
    """
    global _capability_cache
    cap_map = build_capability_map(app)
    enum_caps = enumerate_permission_enum()
    catalog = set(cap_map.keys()) | enum_caps
    _capability_cache = sorted(catalog)
    logger.info(
        "capability catalog registered: %d capabilities (%d route-derived, "
        "%d enum-declared) across %d routes",
        len(_capability_cache),
        len(cap_map),
        len(enum_caps),
        sum(len(v) for v in cap_map.values()),
    )


def get_all_capabilities() -> list[str]:
    """Return the sorted list of all platform capabilities.

    Phase 1: derived from registered routes via :func:`register_capabilities`.
    Phase 2 (SP7): reads from the seeded ``permission`` DB table.

    Returns an empty list (with a warning) if called before
    :func:`register_capabilities` — this happens in some test scenarios.
    """
    if _capability_cache is None:
        logger.warning(
            "get_all_capabilities() called before register_capabilities(app). "
            "Returning empty list. Call register_capabilities(app) after all "
            "routers are registered."
        )
        return []
    return list(_capability_cache)


def reset_capabilities() -> None:
    """Clear the capability cache. For tests only."""
    global _capability_cache
    _capability_cache = None


__all__ = [
    "Permission",
    "build_capability_map",
    "capability",
    "enumerate_permission_enum",
    "get_all_capabilities",
    "get_capability_for_route",
    "register_capabilities",
    "reset_capabilities",
]
