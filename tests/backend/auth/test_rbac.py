"""PDP truth-table tests for SP2.

These are pure unit tests — all SQLAlchemy queries are mocked so the suite
runs without a database or Redis.  The test matrix covers every decision branch
of :class:`~rhesis.backend.app.auth.rbac.DefaultAuthorizationProvider` and the
:func:`~rhesis.backend.app.auth.rbac.authorize` wrapper (fail-closed on
exception, registry swap, etc.).

Also covers:
- :class:`~rhesis.backend.app.routers.base.RhesisRouter` stamping behaviour
- Real-app smoke tests that verify ``register_capabilities`` ran at startup

Test naming convention: ``test_<subject>_<condition>_<expected>``
"""

from __future__ import annotations

import uuid
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.auth.principal import (
    Principal,
    REQUEST_STATE_API_TOKEN_PROJECT_ID,
    REQUEST_STATE_API_TOKEN_SCOPES,
    REQUEST_STATE_AUTH_KIND,
    resolve_principal,
    resolve_principal_from_request,
)
from rhesis.backend.app.auth.rbac import (
    AuthorizationProvider,
    DefaultAuthorizationProvider,
    _AuthorizationRegistry,
    authorize,
    set_authorization_provider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
OTHER_ORG_ID = uuid.uuid4()
OTHER_PROJECT_ID = uuid.uuid4()


def _principal(
    user_id=USER_ID,
    organization_id=ORG_ID,
    kind="session",
) -> Principal:
    return Principal(user_id=user_id, organization_id=organization_id, kind=kind)


def _mock_db(*, is_owner: bool, is_member: bool) -> MagicMock:
    """Build a fake SQLAlchemy session.

    ``db.query(...).filter_by(...).first()`` returns a non-None mock for the
    org-owner query when *is_owner* is True, and for the membership query when
    *is_member* is True.  The two queries are distinguished by checking whether
    the ``filter_by`` call received a ``owner_id`` keyword argument.
    """
    db = MagicMock()

    def _query_side_effect(model):
        q = MagicMock()

        def _filter_by_side_effect(**kwargs):
            fq = MagicMock()
            if "owner_id" in kwargs:
                # This is the org-owner check
                fq.first.return_value = MagicMock() if is_owner else None
            else:
                # This is the project-membership check
                fq.first.return_value = MagicMock() if is_member else None
            return fq

        q.filter_by.side_effect = _filter_by_side_effect
        return q

    db.query.side_effect = _query_side_effect
    return db


# ---------------------------------------------------------------------------
# Principal construction
# ---------------------------------------------------------------------------


class TestPrincipal:
    def test_resolve_principal_maps_user_fields(self):
        user = MagicMock()
        user.id = USER_ID
        user.organization_id = ORG_ID

        p = resolve_principal(user)

        assert p.user_id == USER_ID
        assert p.organization_id == ORG_ID
        assert p.kind == "session"

    def test_principal_is_frozen(self):
        p = _principal()
        with pytest.raises(Exception):
            p.user_id = uuid.uuid4()  # type: ignore[misc]

    def test_principal_equality_ignores_scopes(self):
        p1 = Principal(
            user_id=USER_ID, organization_id=ORG_ID, kind="session", scopes=frozenset(["a"])
        )
        p2 = Principal(
            user_id=USER_ID, organization_id=ORG_ID, kind="session", scopes=frozenset(["b"])
        )
        assert p1 == p2

    def test_principal_equality_ignores_token_project_id(self):
        p1 = Principal(
            user_id=USER_ID, organization_id=ORG_ID, kind="session", token_project_id=PROJECT_ID
        )
        p2 = Principal(
            user_id=USER_ID, organization_id=ORG_ID, kind="session", token_project_id=None
        )
        assert p1 == p2

    # -- REQUEST_STATE_* constants ------------------------------------------

    def test_request_state_constants_have_expected_values(self):
        assert REQUEST_STATE_AUTH_KIND == "auth_kind"
        assert REQUEST_STATE_API_TOKEN_SCOPES == "api_token_scopes"
        assert REQUEST_STATE_API_TOKEN_PROJECT_ID == "api_token_project_id"

    # -- resolve_principal_from_request -------------------------------------

    def _make_request(self, **state_attrs):
        """Return a minimal request-like object with the given state attributes."""
        state = type("State", (), {})()
        for k, v in state_attrs.items():
            setattr(state, k, v)
        req = MagicMock()
        req.state = state
        return req

    def _make_user(self):
        user = MagicMock()
        user.id = USER_ID
        user.organization_id = ORG_ID
        return user

    def test_resolve_from_request_session_auth_defaults(self):
        """No token state → kind='session', scopes=None, token_project_id=None."""
        p = resolve_principal_from_request(self._make_user(), self._make_request())
        assert p.kind == "session"
        assert p.scopes is None
        assert p.token_project_id is None

    def test_resolve_from_request_token_with_scopes_and_project(self):
        """Full token state → kind='token', scopes and project_id propagated."""
        req = self._make_request(
            auth_kind="token",
            api_token_scopes=frozenset({"test_set:read", "endpoint:read"}),
            api_token_project_id=str(PROJECT_ID),
        )
        p = resolve_principal_from_request(self._make_user(), req)
        assert p.kind == "token"
        assert p.scopes == frozenset({"test_set:read", "endpoint:read"})
        assert p.token_project_id == PROJECT_ID

    def test_resolve_from_request_unscoped_token(self):
        """auth_kind='token' with no scopes/project → kind='token', others None."""
        req = self._make_request(auth_kind="token")
        p = resolve_principal_from_request(self._make_user(), req)
        assert p.kind == "token"
        assert p.scopes is None
        assert p.token_project_id is None

    def test_resolve_from_request_invalid_project_id_ignored(self):
        """A non-UUID token_project_id string is silently ignored."""
        req = self._make_request(
            auth_kind="token",
            api_token_project_id="not-a-uuid",
        )
        p = resolve_principal_from_request(self._make_user(), req)
        assert p.kind == "token"
        assert p.token_project_id is None


# ---------------------------------------------------------------------------
# DefaultAuthorizationProvider — truth table
# ---------------------------------------------------------------------------


class TestDefaultAuthorizationProvider:
    """Each test hits a distinct branch of DefaultAuthorizationProvider."""

    def setup_method(self):
        self.provider = DefaultAuthorizationProvider()

    # -- allow cases ---------------------------------------------------------

    def test_org_owner_project_scoped_allowed(self):
        """Org owner is allowed for any project-scoped permission."""
        p = _principal()
        db = _mock_db(is_owner=True, is_member=False)
        assert self.provider.is_authorized(p, "test_set:read", project_id=PROJECT_ID, db=db)

    def test_org_owner_org_scoped_allowed(self):
        """Org owner is allowed for org-scoped permissions (project_id=None)."""
        p = _principal()
        db = _mock_db(is_owner=True, is_member=False)
        assert self.provider.is_authorized(p, "organization:update", project_id=None, db=db)

    def test_project_member_project_scoped_allowed(self):
        """Non-owner project member is allowed for project-scoped permissions."""
        p = _principal()
        db = _mock_db(is_owner=False, is_member=True)
        assert self.provider.is_authorized(p, "test_set:read", project_id=PROJECT_ID, db=db)

    def test_project_member_any_action_allowed(self):
        """Project membership grants all project-scoped actions in community tier."""
        p = _principal()
        db = _mock_db(is_owner=False, is_member=True)
        for action in ("test_set:delete", "test_run:execute", "endpoint:create"):
            assert self.provider.is_authorized(p, action, project_id=PROJECT_ID, db=db), action

    # -- deny cases ----------------------------------------------------------

    def test_no_org_context_denied(self):
        """Principal with no organization is always denied."""
        p = Principal(user_id=USER_ID, organization_id=None, kind="session")
        db = _mock_db(is_owner=False, is_member=False)
        assert not self.provider.is_authorized(p, "test_set:read", project_id=PROJECT_ID, db=db)

    def test_non_member_project_scoped_denied(self):
        """User who is neither owner nor project member is denied."""
        p = _principal()
        db = _mock_db(is_owner=False, is_member=False)
        assert not self.provider.is_authorized(p, "test_set:read", project_id=PROJECT_ID, db=db)

    def test_project_member_org_scoped_denied(self):
        """Project member (non-owner) cannot perform org-scoped actions."""
        p = _principal()
        db = _mock_db(is_owner=False, is_member=True)
        assert not self.provider.is_authorized(
            p, "organization:update", project_id=None, db=db
        )

    def test_non_member_owner_only_capability_denied(self):
        """Non-owner cannot invoke owner-only capabilities (e.g. organization:update)."""
        p = _principal()
        db = _mock_db(is_owner=False, is_member=False)
        assert not self.provider.is_authorized(p, "organization:update", project_id=None, db=db)

    def test_non_owner_standard_capability_allowed(self):
        """Any org member may invoke standard (non-owner-only) capabilities without project scope.

        The ORM scope already limits rows to the caller's organization, so no extra
        gate is needed for capabilities like test_set:read, project:create, etc.
        """
        p = _principal()
        db = _mock_db(is_owner=False, is_member=False)
        for cap in ("test_set:read", "project:create", "organization:read"):
            assert self.provider.is_authorized(p, cap, project_id=None, db=db), (
                f"Expected org member to be allowed for '{cap}' without project scope"
            )

    def test_project_member_wrong_project_denied(self):
        """Being a member of project A doesn't grant access to project B.

        Simulated by returning is_member=False (the DB query wouldn't match
        the wrong project_id).
        """
        p = _principal()
        db = _mock_db(is_owner=False, is_member=False)
        assert not self.provider.is_authorized(
            p, "test_set:read", project_id=OTHER_PROJECT_ID, db=db
        )

    def test_owner_of_other_org_denied(self):
        """Being the owner of a *different* organization grants nothing here.

        The filter_by(id=ORG_ID, owner_id=USER_ID) won't match if the DB row
        has a different org_id — simulated by is_owner=False.
        """
        p = Principal(user_id=USER_ID, organization_id=OTHER_ORG_ID, kind="session")
        db = _mock_db(is_owner=False, is_member=False)
        assert not self.provider.is_authorized(p, "test_set:read", project_id=PROJECT_ID, db=db)


# ---------------------------------------------------------------------------
# authorize() wrapper
# ---------------------------------------------------------------------------


class TestAuthorize:
    """Tests for the module-level authorize() function."""

    def setup_method(self):
        _AuthorizationRegistry.reset()

    def teardown_method(self):
        _AuthorizationRegistry.reset()

    def test_authorize_delegates_to_provider(self):
        p = _principal()
        db = _mock_db(is_owner=True, is_member=False)
        assert authorize(p, "test_set:read", project_id=PROJECT_ID, db=db)

    def test_authorize_fail_closed_on_exception(self):
        """An unexpected provider exception must return False, never propagate."""
        p = _principal()
        db = MagicMock()
        db.query.side_effect = RuntimeError("unexpected DB error")
        # Should not raise — fail-closed
        result = authorize(p, "test_set:read", project_id=PROJECT_ID, db=db)
        assert result is False

    def test_authorize_uses_custom_provider(self):
        """set_authorization_provider replaces the active provider."""

        class AlwaysAllowProvider(AuthorizationProvider):
            def is_authorized(self, principal, permission, *, project_id, db):
                return True

        set_authorization_provider(AlwaysAllowProvider())
        p = _principal()
        db = MagicMock()
        assert authorize(p, "anything:delete", project_id=None, db=db) is True

    def test_authorize_registry_reset_restores_default(self):
        """_AuthorizationRegistry.reset() restores DefaultAuthorizationProvider."""

        class AlwaysAllowProvider(AuthorizationProvider):
            def is_authorized(self, principal, permission, *, project_id, db):
                return True

        set_authorization_provider(AlwaysAllowProvider())
        _AuthorizationRegistry.reset()

        # Default provider: non-owner, non-member → deny
        p = _principal()
        db = _mock_db(is_owner=False, is_member=False)
        assert authorize(p, "test_set:read", project_id=PROJECT_ID, db=db) is False

    def test_authorize_base_provider_always_denies(self):
        """The base AuthorizationProvider class is fail-closed (deny all)."""
        set_authorization_provider(AuthorizationProvider())
        p = _principal()
        db = MagicMock()
        assert authorize(p, "test_set:read", project_id=PROJECT_ID, db=db) is False


# ---------------------------------------------------------------------------
# Capabilities module
# ---------------------------------------------------------------------------


class TestCapabilities:
    def setup_method(self):
        from rhesis.backend.app.auth.capabilities import reset_capabilities
        reset_capabilities()

    def teardown_method(self):
        from rhesis.backend.app.auth.capabilities import reset_capabilities
        reset_capabilities()

    # --- @capability() decorator ---

    def test_capability_decorator_returns_openapi_extra(self):
        from rhesis.backend.app.auth.capabilities import capability

        result = capability("test_set:generate")
        assert result == {"openapi_extra": {"x-rhesis-capability": "test_set:generate"}}

    def test_capability_decorator_can_be_unpacked(self):
        from rhesis.backend.app.auth.capabilities import capability

        kwargs = {**capability("test:execute")}
        assert "openapi_extra" in kwargs

    # --- get_capability_for_route ---

    def test_get_capability_for_route_explicit_marker_wins(self):
        """x-rhesis-capability overrides any resource+verb convention."""
        from rhesis.backend.app.auth.capabilities import get_capability_for_route

        route = MagicMock()
        route.path = "/test_sets/generate"
        route.openapi_extra = {
            "x-rhesis-capability": "test_set:generate",
            "x-rhesis-resource": "test_set",
        }
        route.methods = {"POST"}

        assert get_capability_for_route(route) == "test_set:generate"

    def test_get_capability_for_route_resource_plus_verb_get(self):
        """Resource stamp + GET → resource:read."""
        from rhesis.backend.app.auth.capabilities import get_capability_for_route

        route = MagicMock()
        route.path = "/test_sets/{id}"
        route.openapi_extra = {"x-rhesis-resource": "test_set"}
        route.methods = {"GET"}

        assert get_capability_for_route(route) == "test_set:read"

    def test_get_capability_for_route_resource_plus_verb_delete(self):
        from rhesis.backend.app.auth.capabilities import get_capability_for_route

        route = MagicMock()
        route.path = "/test_sets/{id}"
        route.openapi_extra = {"x-rhesis-resource": "test_set"}
        route.methods = {"DELETE"}

        assert get_capability_for_route(route) == "test_set:delete"

    def test_get_capability_for_route_no_resource_returns_none(self):
        """Routes without x-rhesis-resource AND without explicit capability return None."""
        from rhesis.backend.app.auth.capabilities import get_capability_for_route

        route = MagicMock()
        route.path = "/some/internal/route"
        route.openapi_extra = {}
        route.methods = {"GET"}

        assert get_capability_for_route(route) is None

    def test_get_capability_for_route_skip_path(self):
        from rhesis.backend.app.auth.capabilities import get_capability_for_route

        route = MagicMock()
        route.path = "/health"
        route.openapi_extra = {"x-rhesis-resource": "ignored"}
        route.methods = {"GET"}

        assert get_capability_for_route(route) is None

    # --- build_capability_map / register_capabilities / get_all_capabilities ---

    def _make_app(self, routes):
        """Build a minimal fake FastAPI app with given route specs."""
        from fastapi.routing import APIRoute
        app = MagicMock()
        api_routes = []
        for path, methods, extra in routes:
            r = MagicMock(spec=APIRoute)
            r.path = path
            r.methods = methods
            r.openapi_extra = extra
            api_routes.append(r)
        app.router.routes = api_routes
        return app

    def test_build_capability_map_derives_from_resource_stamp(self):
        from rhesis.backend.app.auth.capabilities import build_capability_map

        app = self._make_app([
            ("/behaviors", {"GET"}, {"x-rhesis-resource": "behavior"}),
            ("/behaviors", {"POST"}, {"x-rhesis-resource": "behavior"}),
            ("/behaviors/{id}", {"DELETE"}, {"x-rhesis-resource": "behavior"}),
        ])
        cap_map = build_capability_map(app)
        assert "behavior:read" in cap_map
        assert "behavior:create" in cap_map
        assert "behavior:delete" in cap_map

    def test_build_capability_map_explicit_capability_wins(self):
        from rhesis.backend.app.auth.capabilities import build_capability_map

        app = self._make_app([
            ("/test_sets/generate", {"POST"}, {
                "x-rhesis-capability": "test_set:generate",
                "x-rhesis-resource": "test_set",
            }),
        ])
        cap_map = build_capability_map(app)
        assert "test_set:generate" in cap_map
        assert "test_set:create" not in cap_map

    def test_register_and_get_all_capabilities(self):
        from rhesis.backend.app.auth.capabilities import (
            register_capabilities,
            get_all_capabilities,
        )

        app = self._make_app([
            ("/behaviors", {"GET"}, {"x-rhesis-resource": "behavior"}),
            ("/behaviors", {"POST"}, {"x-rhesis-resource": "behavior"}),
            ("/test_sets/{id}", {"DELETE"}, {"x-rhesis-resource": "test_set"}),
        ])
        register_capabilities(app)
        caps = get_all_capabilities()
        assert isinstance(caps, list)
        assert caps == sorted(caps)
        assert "behavior:read" in caps
        assert "behavior:create" in caps
        assert "test_set:delete" in caps

    def test_get_all_capabilities_before_register_returns_empty(self):
        """get_all_capabilities() returns [] (with warning) before registration."""
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        assert get_all_capabilities() == []

    def test_register_capabilities_is_idempotent(self):
        """Calling register_capabilities twice replaces the cache cleanly."""
        from rhesis.backend.app.auth.capabilities import (
            register_capabilities,
            get_all_capabilities,
        )

        app1 = self._make_app([("/behaviors", {"GET"}, {"x-rhesis-resource": "behavior"})])
        app2 = self._make_app([("/risks", {"GET"}, {"x-rhesis-resource": "risk"})])

        register_capabilities(app1)
        assert "behavior:read" in get_all_capabilities()

        register_capabilities(app2)
        caps = get_all_capabilities()
        assert "risk:read" in caps
        assert "behavior:read" not in caps  # replaced, not merged


# ---------------------------------------------------------------------------
# RhesisRouter stamping
# ---------------------------------------------------------------------------


class TestRhesisRouter:
    """Verify that RhesisRouter injects x-rhesis-resource into every route it owns."""

    def test_resource_stamped_on_route(self):
        from rhesis.backend.app.routers.base import RhesisRouter

        router = RhesisRouter(prefix="/things", resource="thing")

        @router.get("/")
        def list_things():
            return []

        route = router.routes[0]
        assert route.openapi_extra.get("x-rhesis-resource") == "thing"

    def test_all_routes_on_same_router_are_stamped(self):
        from rhesis.backend.app.routers.base import RhesisRouter

        router = RhesisRouter(prefix="/things", resource="thing")

        @router.get("/")
        def list_things():
            return []

        @router.post("/")
        def create_thing():
            return {}

        @router.delete("/{id}")
        def delete_thing():
            return {}

        for route in router.routes:
            assert route.openapi_extra.get("x-rhesis-resource") == "thing", (
                f"Route {route.path} was not stamped with x-rhesis-resource"
            )

    def test_explicit_capability_preserved_alongside_resource(self):
        """@capability() extra should sit alongside x-rhesis-resource, not replace it."""
        from rhesis.backend.app.auth.capabilities import capability
        from rhesis.backend.app.routers.base import RhesisRouter

        router = RhesisRouter(prefix="/things", resource="thing")

        @router.post("/generate", **capability("thing:generate"))
        def generate():
            return {}

        route = router.routes[0]
        extra = route.openapi_extra
        assert extra.get("x-rhesis-resource") == "thing"
        assert extra.get("x-rhesis-capability") == "thing:generate"

    def test_explicit_capability_wins_in_deriver(self):
        """get_capability_for_route prefers x-rhesis-capability over verb derivation."""
        from rhesis.backend.app.auth.capabilities import capability, get_capability_for_route
        from rhesis.backend.app.routers.base import RhesisRouter

        router = RhesisRouter(prefix="/things", resource="thing")

        @router.post("/generate", **capability("thing:generate"))
        def generate():
            return {}

        cap = get_capability_for_route(router.routes[0])
        assert cap == "thing:generate"

    def test_plain_apirouter_produces_no_resource_stamp(self):
        from fastapi import APIRouter

        router = APIRouter(prefix="/things")

        @router.get("/")
        def list_things():
            return []

        extra = getattr(router.routes[0], "openapi_extra", None) or {}
        assert "x-rhesis-resource" not in extra

    def test_router_without_resource_kwarg_produces_no_stamp(self):
        """RhesisRouter(resource=None) must not inject any x-rhesis-resource key."""
        from rhesis.backend.app.routers.base import RhesisRouter

        router = RhesisRouter(prefix="/things")  # no resource= passed

        @router.get("/")
        def list_things():
            return []

        extra = getattr(router.routes[0], "openapi_extra", None) or {}
        assert "x-rhesis-resource" not in extra


# ---------------------------------------------------------------------------
# Real-app smoke tests
# ---------------------------------------------------------------------------


class TestRealAppCapabilities:
    """
    Smoke tests that re-register capabilities against the live FastAPI app
    and verify the full route → capability pipeline end-to-end.

    These are still pure unit tests (no DB, no HTTP).  We call
    ``register_capabilities(app)`` explicitly in setup so this class is
    independent of module-import order (earlier tests may have called
    ``reset_capabilities()`` in their teardown).
    """

    def setup_method(self):
        from rhesis.backend.app.auth.capabilities import register_capabilities
        from rhesis.backend.app.main import app

        register_capabilities(app)

    def teardown_method(self):
        from rhesis.backend.app.auth.capabilities import reset_capabilities

        reset_capabilities()

    def test_capabilities_registered_and_non_empty(self):
        from rhesis.backend.app.auth.capabilities import get_all_capabilities

        caps = get_all_capabilities()
        assert isinstance(caps, list)
        assert len(caps) > 0, "Expected at least one capability to be registered"

    def test_capabilities_are_sorted(self):
        from rhesis.backend.app.auth.capabilities import get_all_capabilities

        caps = get_all_capabilities()
        assert caps == sorted(caps), "Capabilities list should be in sorted order"

    def test_core_crud_capabilities_present(self):
        """A representative set of plain CRUD capabilities must be derived."""
        from rhesis.backend.app.auth.capabilities import get_all_capabilities

        cap_set = set(get_all_capabilities())
        required = {
            "test_set:read",
            "test_set:create",
            "test_set:update",
            "test_set:delete",
            "behavior:read",
            "behavior:create",
            "behavior:update",
            "behavior:delete",
            "organization:read",
            "member:read",
        }
        missing = required - cap_set
        assert not missing, f"Missing expected CRUD capabilities: {missing}"

    def test_explicit_capability_overrides_present(self):
        """Capabilities declared with @capability() must survive into the registry."""
        from rhesis.backend.app.auth.capabilities import get_all_capabilities

        cap_set = set(get_all_capabilities())
        explicit_caps = {
            "test_set:generate",
            "test_set:execute",
            "comment:react",
            "recycle:restore",
            "project_member:manage",
        }
        missing = explicit_caps - cap_set
        assert not missing, f"Missing explicit @capability() overrides: {missing}"

    def test_no_verb_drift_on_execute_path(self):
        """
        POST /test_sets/{id}/execute must yield test_set:execute (explicit),
        not the default POST→create derivation.
        """
        from rhesis.backend.app.auth.capabilities import build_capability_map, get_all_capabilities
        from rhesis.backend.app.main import app

        cap_set = set(get_all_capabilities())
        assert "test_set:execute" in cap_set

        cap_map = build_capability_map(app)
        execute_paths = cap_map.get("test_set:execute", [])
        assert any("execute" in p for p in execute_paths), (
            f"test_set:execute not mapped to any 'execute' path; got: {execute_paths}"
        )

    def test_capabilities_all_have_resource_action_format(self):
        """Every capability must match ``resource:action`` (optionally ``:own``).

        The optional ``:own`` qualifier is the object-level capability form (SP10),
        e.g. ``comment:update:own`` — see ``authorize_object``.
        """
        import re

        from rhesis.backend.app.auth.capabilities import get_all_capabilities

        pattern = re.compile(r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*(:own)?$")
        for cap in get_all_capabilities():
            assert pattern.match(cap), f"Capability '{cap}' does not match resource:action format"
