"""Tests for the app-level authentication backstop (apply_auth_backstop).

Regression coverage for the onboarding "not associated with an organization"
bug: the backstop must not stack the org-requiring
``require_current_user_or_token`` on top of routes that intentionally declare
the context-free ``require_current_user_or_token_without_context`` so brand-new
users with no organization can complete onboarding.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute

from rhesis.backend.app.auth.user_utils import (
    require_current_user,
    require_current_user_or_token,
    require_current_user_or_token_without_context,
)
from rhesis.backend.app.main import apply_auth_backstop


def _collect_dependency_calls(dependant, seen=None) -> set:
    """Return every dependency callable in a route's dependant tree."""
    if seen is None:
        seen = set()
    calls = set()
    for sub in dependant.dependencies:
        call = getattr(sub, "call", None)
        if call is not None:
            calls.add(call)
            if id(call) not in seen:
                seen.add(id(call))
                calls |= _collect_dependency_calls(sub, seen)
    return calls


def _find_route(app: FastAPI, path: str, method: str) -> APIRoute:
    for route in app.router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route {method} {path} not found")


@pytest.mark.unit
class TestAuthBackstop:
    """The backstop protects unauthenticated routes without breaking onboarding."""

    def test_create_organization_keeps_context_free_auth(self):
        """POST /organizations/ must stay org-optional for onboarding."""
        from rhesis.backend.app.main import app

        route = _find_route(app, "/organizations/", "POST")
        calls = _collect_dependency_calls(route.dependant)

        assert require_current_user_or_token_without_context in calls
        # The backstop must NOT have stacked the org-requiring variant on top,
        # which would 403 brand-new users who have no organization yet.
        assert require_current_user_or_token not in calls

    def test_update_user_keeps_context_free_auth(self):
        """PUT /users/{user_id} must stay org-optional for onboarding."""
        from rhesis.backend.app.main import app

        route = _find_route(app, "/users/{user_id}", "PUT")
        calls = _collect_dependency_calls(route.dependant)

        assert require_current_user_or_token_without_context in calls
        assert require_current_user_or_token not in calls

    def test_backstop_injects_on_unprotected_route(self):
        """A route with no auth dependency gets the baseline injected."""
        app = FastAPI()

        @app.get("/wide-open")
        def wide_open():
            return {"ok": True}

        @app.get("/already-auth")
        def already_auth(_user=Depends(require_current_user)):
            return {"ok": True}

        apply_auth_backstop(app)

        unprotected = _find_route(app, "/wide-open", "GET")
        assert require_current_user_or_token in _collect_dependency_calls(unprotected.dependant)

        # A route that already authenticates is left untouched (its own policy
        # remains authoritative; the org-requiring backstop is not stacked on).
        protected = _find_route(app, "/already-auth", "GET")
        protected_calls = _collect_dependency_calls(protected.dependant)
        assert require_current_user in protected_calls
        assert require_current_user_or_token not in protected_calls

    def test_backstop_skips_public_routes(self):
        """Routes listed in PUBLIC_ROUTES never get the baseline injected."""
        from rhesis.backend.app.auth.public_routes import PUBLIC_ROUTES

        app = FastAPI()

        public_path = "/health"
        assert public_path in PUBLIC_ROUTES

        @app.get(public_path)
        def health():
            return {"status": "ok"}

        apply_auth_backstop(app)

        route = _find_route(app, public_path, "GET")
        assert require_current_user_or_token not in _collect_dependency_calls(route.dependant)
