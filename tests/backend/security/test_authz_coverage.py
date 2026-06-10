"""PEP coverage / drift guard — SP4.

Every registered ``APIRoute`` must satisfy one of the following conditions:

1. Its path is in :data:`~rhesis.backend.app.auth.public_routes.PUBLIC_ROUTES`
   (no authentication required, so no authorisation check is needed either).
2. Its ``(HTTP_METHOD, path)`` pair is in
   :data:`~rhesis.backend.app.auth.public_routes.AUTHZ_EXEMPT_ROUTES`
   (authenticated but deliberately exempt from the permission check — e.g.
   onboarding, bootstrap endpoints).
3. Its path is in the capability deriver's skip list (``/``, ``/health``,
   ``/docs``, ``/openapi.json``, ``/redoc`` — system / infrastructure routes).
4. :func:`~rhesis.backend.app.auth.capabilities.get_capability_for_route`
   returns a non-``None`` capability string (so ``apply_authz_backstop`` will
   inject ``require_permission``).

Any route that falls through all four conditions is *unmapped* — it has no
permission check and is not consciously exempt.  This test fails the build so
that unmapped routes are caught at PR time rather than in production.

Additionally, this test asserts that the retired ``ResourcePermission`` class
and ``@check_resource_permission`` decorator are no longer importable, so they
cannot creep back.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.routing import APIRoute

from rhesis.backend.app.auth.capabilities import (
    _DERIVER_SKIP_PATHS,
    get_capability_for_route,
)
from rhesis.backend.app.auth.public_routes import AUTHZ_EXEMPT_ROUTES, PUBLIC_ROUTES
from rhesis.backend.app.main import app


# ---------------------------------------------------------------------------
# Drift guard: every route must be mapped or explicitly exempted
# ---------------------------------------------------------------------------


@pytest.mark.security
class TestAuthzCoverage:
    """PEP coverage guard — fails if any route slips through without a capability."""

    def test_every_route_is_mapped_or_exempt(self):
        """Every HTTP route must have a capability or be in an exempt list.

        Failure message lists the offending routes and explains how to fix them:
        - Add ``resource=`` to the enclosing ``RhesisRouter`` (standard CRUD), or
        - Add ``**capability(Permission.X.Y)`` to the route decorator (non-CRUD), or
        - Add ``(METHOD, path)`` to ``AUTHZ_EXEMPT_ROUTES`` with a justification.
        """
        unmapped: list[str] = []

        for route in app.router.routes:
            if not isinstance(route, APIRoute):
                continue
            path: str = route.path
            methods: set[str] = route.methods or set()

            # Skip: no authentication required
            if path in PUBLIC_ROUTES:
                continue

            # Skip: authenticated but authz-exempt for this verb
            if any((m, path) in AUTHZ_EXEMPT_ROUTES for m in methods):
                continue

            # Skip: infrastructure / system routes in the deriver skip-list
            if path in _DERIVER_SKIP_PATHS:
                continue

            cap = get_capability_for_route(route)
            if cap is None:
                unmapped.append(f"{sorted(methods)}: {path}")

        assert not unmapped, (
            f"\n{len(unmapped)} route(s) have no capability mapping and are not in "
            "PUBLIC_ROUTES or AUTHZ_EXEMPT_ROUTES:\n\n"
            + "\n".join(f"  {r}" for r in sorted(unmapped))
            + "\n\nFix options:\n"
            "  1. Standard CRUD route: ensure the enclosing router is a RhesisRouter "
            "with resource= set.\n"
            "  2. Non-CRUD route: add **capability(Permission.X.Y) to the decorator.\n"
            "  3. Legitimately exempt: add (METHOD, path) to AUTHZ_EXEMPT_ROUTES in "
            "auth/public_routes.py with a comment explaining why."
        )

    def test_all_exemptions_reference_real_routes(self):
        """Every entry in AUTHZ_EXEMPT_ROUTES must correspond to a real registered route.

        Stale entries indicate that a route was renamed or deleted without updating
        the allowlist, which silently widens the exempt surface.
        """
        registered: set[tuple[str, str]] = set()
        for route in app.router.routes:
            if not isinstance(route, APIRoute):
                continue
            for method in route.methods or set():
                registered.add((method, route.path))

        stale = [
            f"{m} {p}" for m, p in sorted(AUTHZ_EXEMPT_ROUTES) if (m, p) not in registered
        ]
        assert not stale, (
            f"AUTHZ_EXEMPT_ROUTES contains entries that don't match any registered route "
            f"(remove or update them):\n" + "\n".join(f"  {s}" for s in stale)
        )


# ---------------------------------------------------------------------------
# Retirement guard: ResourcePermission and @check_resource_permission must be gone
# ---------------------------------------------------------------------------


@pytest.mark.security
class TestRetiredResourcePermission:
    """Asserts that the retired ResourcePermission machinery is fully removed."""

    def test_resource_permission_module_is_gone(self):
        """auth.permissions must not export ResourcePermission.

        The module itself may still exist as a tombstone but the class must be absent.
        Importing should either raise ImportError (module deleted) or the class should
        not be an attribute.
        """
        try:
            perms = importlib.import_module("rhesis.backend.app.auth.permissions")
            assert not hasattr(perms, "ResourcePermission"), (
                "ResourcePermission still lives in auth.permissions — retire it by "
                "deleting the class (the PEP backstop now enforces all permissions)."
            )
        except ImportError:
            pass  # Module deleted — ideal outcome.

    def test_check_resource_permission_decorator_is_gone(self):
        """auth.decorators.check_resource_permission must not be importable.

        The decorator was the call site for ResourcePermission on test_set routes;
        its removal confirms the migration to the PEP backstop is complete.
        """
        try:
            decs = importlib.import_module("rhesis.backend.app.auth.decorators")
            assert not hasattr(decs, "check_resource_permission"), (
                "check_resource_permission still lives in auth.decorators — remove it "
                "(the PEP backstop now enforces all permissions)."
            )
        except ImportError:
            pass  # Module deleted — ideal outcome.

    def test_test_set_router_does_not_import_retired_symbols(self):
        """test_set.py must not import check_resource_permission or ResourceAction.

        This verifies the migration is complete at the import level — a stale import
        that doesn't cause a NameError at runtime would otherwise go unnoticed.
        """
        import inspect

        from rhesis.backend.app.routers import test_set as ts_module

        source = inspect.getsource(ts_module)
        assert "check_resource_permission" not in source, (
            "test_set.py still references check_resource_permission — remove the decorator "
            "and its import."
        )
        assert "from rhesis.backend.app.auth.permissions import" not in source, (
            "test_set.py still imports from auth.permissions — remove the import."
        )
