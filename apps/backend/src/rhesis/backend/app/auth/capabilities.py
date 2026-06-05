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
from typing import Optional

logger = logging.getLogger(__name__)

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


def capability(name: str) -> dict:
    """Return ``openapi_extra`` kwargs marking a route with an explicit capability.

    Unpack into the FastAPI route decorator for non-CRUD routes whose action
    cannot be inferred from the HTTP verb alone::

        @router.post("/generate", **capability("test_set:generate"))
        async def generate_test_set(...):
            ...

    The deriver checks for this key first; it overrides the resource+verb
    convention when both are present.
    """
    return {"openapi_extra": {_CAPABILITY_KEY: name}}


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


def register_capabilities(app: object) -> None:
    """Derive and cache the full capability catalog from registered routes.

    Must be called **once**, from ``main.py``, after all routers (core + EE)
    have been included and *after* :func:`apply_auth_backstop` has run (so EE
    routes are visible).

    Idempotent: re-calling replaces the cache (useful in tests that rebuild
    the app).
    """
    global _capability_cache
    cap_map = build_capability_map(app)
    _capability_cache = sorted(cap_map.keys())
    logger.info(
        "capability catalog registered: %d capabilities across %d routes",
        len(_capability_cache),
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
    "build_capability_map",
    "capability",
    "get_all_capabilities",
    "get_capability_for_route",
    "register_capabilities",
    "reset_capabilities",
]
