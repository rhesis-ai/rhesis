"""The MCP tool list only offers tools the caller can use.

Each tool resolves to a FastAPI route, and the route says what it needs: a
capability (the authz backstop's) and, for Enterprise routes, a feature
(``require_feature``). ``visible_tools`` keeps a tool when both are met.
Role-based cases need the EE provider and live in
``tests/backend/ee/rbac/test_mcp_tool_visibility.py``.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import APIRouter, Depends, FastAPI

from rhesis.backend.app.auth.feature_gates import feature_for_route, require_feature
from rhesis.backend.app.auth.principal import AuthKind, Principal
from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.app.mcp_server import tools as mcp_tools
from rhesis.backend.app.mcp_server.tools import (
    build_tools_and_operations,
    load_tool_configs,
    visible_tools,
)


def _route(app: FastAPI, path: str):
    return next(r for r in app.router.routes if getattr(r, "path", None) == path)


def _gated_app() -> FastAPI:
    app = FastAPI()

    @app.get("/plain")
    def plain():
        return {}

    @app.get("/gated", dependencies=[Depends(require_feature(FeatureName.SSO))])
    def gated():
        return {}

    def nested(_org=Depends(require_feature(FeatureName.RBAC))):
        return None

    @app.get("/nested")
    def nested_route(_n=Depends(nested)):
        return {}

    router = APIRouter(dependencies=[Depends(require_feature(FeatureName.API_CLIENTS))])

    @router.get("/router-gated")
    def router_gated():
        return {}

    app.include_router(router)
    return app


@pytest.mark.unit
class TestFeatureForRoute:
    def test_ungated_route_has_no_feature(self):
        assert feature_for_route(_route(_gated_app(), "/plain")) is None

    def test_route_dependency_is_found(self):
        assert feature_for_route(_route(_gated_app(), "/gated")) == "sso"

    def test_router_dependency_is_found(self):
        assert feature_for_route(_route(_gated_app(), "/router-gated")) == "api_clients"

    def test_gate_inside_a_sub_dependency_is_found(self):
        assert feature_for_route(_route(_gated_app(), "/nested")) == "rbac"

    def test_object_without_dependant_has_no_feature(self):
        assert feature_for_route(object()) is None


@pytest.mark.unit
class TestOperationMetadata:
    def test_feature_reaches_the_operation_map(self):
        configs = [
            {"name": "plain_tool", "method": "GET", "path": "/plain"},
            {"name": "gated_tool", "method": "GET", "path": "/gated"},
        ]
        _, operations = build_tools_and_operations(_gated_app(), tool_configs=configs)
        assert operations["plain_tool"]["feature"] is None
        assert operations["gated_tool"]["feature"] == "sso"


@pytest.mark.unit
class TestEveryToolResolvesToAGatedRoute:
    """The first automated check that mcp_tools.yaml matches real routes.

    A tool whose path matches no route vanishes from the list with only a
    warning, and a route with no capability would be offered to everyone.
    """

    def test_every_tool_builds(self):
        from rhesis.backend.app.main import app

        tools, _ = build_tools_and_operations(app)
        built = {t.name for t in tools}
        missing = [tc["name"] for tc in load_tool_configs() if tc["name"] not in built]
        assert not missing, f"tools whose method/path match no route: {missing}"

    def test_every_tool_has_a_capability(self):
        from rhesis.backend.app.main import app

        _, operations = build_tools_and_operations(app)
        unmapped = [name for name, op in operations.items() if not op["capability"]]
        assert not unmapped, f"tools whose route enforces no capability: {unmapped}"


def _principal() -> Principal:
    return Principal(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), kind=AuthKind.SESSION)


_OPERATIONS = {
    "list_things": {"capability": "thing:read", "feature": None},
    "create_thing": {"capability": "thing:create", "feature": None},
    "list_sso_things": {"capability": "thing:read", "feature": "sso"},
}


class _License:
    def __init__(self, allowed: bool):
        self.allowed = allowed

    def allows_feature(self, feature, org) -> bool:
        return self.allowed

    def info(self, org=None) -> dict:
        return {}


@pytest.fixture
def held(monkeypatch):
    """Stand in for effective_permissions so these tests need no database."""
    caps: set[str] = set()
    monkeypatch.setattr(mcp_tools, "effective_permissions", lambda *a, **kw: sorted(caps))
    return caps


@pytest.fixture
def sso_registered(monkeypatch):
    monkeypatch.setattr(FeatureRegistry, "_features", {})
    FeatureRegistry.register(Feature(name=FeatureName.SSO))


def _visible(org=object()):
    return visible_tools(_OPERATIONS, _principal(), org, project_id=None, db=None)


@pytest.mark.unit
class TestVisibleTools:
    def test_capability_decides(self, held, sso_registered):
        held.add("thing:read")
        assert "list_things" in _visible()
        assert "create_thing" not in _visible()

    def test_no_capabilities_means_no_tools(self, held, sso_registered):
        assert _visible() == frozenset()

    def test_community_org_does_not_see_ee_tools(self, held, sso_registered, monkeypatch):
        held.update({"thing:read", "thing:create"})
        monkeypatch.setattr(FeatureRegistry, "_license", _License(allowed=False))
        assert _visible() == {"list_things", "create_thing"}

    def test_entitled_org_sees_ee_tools(self, held, sso_registered, monkeypatch):
        held.update({"thing:read", "thing:create"})
        monkeypatch.setattr(FeatureRegistry, "_license", _License(allowed=True))
        assert _visible() == {"list_things", "create_thing", "list_sso_things"}

    def test_unregistered_feature_hides_the_tool(self, held, monkeypatch):
        """A Community build never registers EE features."""
        monkeypatch.setattr(FeatureRegistry, "_features", {})
        held.add("thing:read")
        assert "list_sso_things" not in _visible()

    def test_ee_tool_needs_its_capability_too(self, held, sso_registered, monkeypatch):
        monkeypatch.setattr(FeatureRegistry, "_license", _License(allowed=True))
        held.add("thing:create")
        assert "list_sso_things" not in _visible()

    def test_missing_organization_hides_ee_tools(self, held, sso_registered, monkeypatch):
        monkeypatch.setattr(FeatureRegistry, "_license", _License(allowed=True))
        held.add("thing:read")
        assert "list_sso_things" not in _visible(org=None)
