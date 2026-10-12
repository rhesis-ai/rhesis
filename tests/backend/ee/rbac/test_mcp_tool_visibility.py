"""Role and token scope shape the MCP tool list, for MCP clients and the Architect.

Filtering is for usability only: a hidden tool called directly still fails at
its route.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_mcp_tool_visibility.py -v
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import contextmanager
from datetime import datetime

import mcp.types as mcp_types
import pytest
from fastapi import status
from mcp.server.lowlevel.server import request_ctx
from mcp.shared.context import RequestContext
from sqlalchemy.orm import Session
from starlette.requests import Request

from rhesis.backend.app import dependencies
from rhesis.backend.app.auth.oauth_scope import capabilities_for_oauth_scope
from rhesis.backend.app.auth.principal import (
    REQUEST_STATE_API_TOKEN_SCOPES,
    REQUEST_STATE_AUTH_KIND,
    AuthKind,
    Principal,
    resolve_principal,
)
from rhesis.backend.app.mcp_server import tools as mcp_tools
from rhesis.backend.app.mcp_server.local_tools import LocalToolProvider
from rhesis.backend.app.mcp_server.server import _create_mcp_server
from rhesis.backend.app.mcp_server.tools import build_tools_and_operations, visible_tools_for
from tests.backend.ee.rbac._rbac_helpers import _assign_org_role, _ee_provider_active, _rbac_enabled
from tests.backend.fixtures.test_setup import create_test_organization_and_user

_WRITE_PREFIXES = ("create_", "update_")


def _make_user(test_db: Session, role_name: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    org, user, token = create_test_organization_and_user(
        test_db,
        f"MCP Tool Visibility {role_name} {ts}_{suffix}",
        f"mcp_tools_{role_name.lower()}_{suffix}@rhesis-test.com",
        f"MCP {role_name}",
    )
    org.owner_id = None
    test_db.flush()
    _assign_org_role(test_db, org.id, user.id, role_name)
    test_db.commit()
    return org, user, token


@pytest.fixture(autouse=True)
def tenant_sessions_use_test_db(test_db, monkeypatch):
    """The visibility check opens its own sessions; point them at ``test_db``."""

    @contextmanager
    def _fake(*_args, **_kwargs):
        yield test_db

    monkeypatch.setattr(mcp_tools, "get_db_with_tenant_variables", _fake)
    monkeypatch.setattr(dependencies, "get_db_with_tenant_variables", _fake)


@pytest.fixture(scope="module")
def app():
    from rhesis.backend.app.main import app

    return app


@pytest.fixture(scope="module")
def operations(app):
    _, ops = build_tools_and_operations(app)
    return ops


def _visible(operations, principal: Principal) -> frozenset[str]:
    with _ee_provider_active(), _rbac_enabled():
        return visible_tools_for(operations, principal, None)


def _read_tools(operations) -> set[str]:
    return {name for name, op in operations.items() if op["capability"].endswith(":read")}


@pytest.mark.ee
@pytest.mark.integration
class TestRoleShapesTheToolList:
    def test_viewer_sees_reads_but_no_writes(self, test_db, operations):
        _org, user, _token = _make_user(test_db, "Viewer")
        visible = _visible(operations, resolve_principal(user))

        assert {"list_metrics", "get_test_run", "list_endpoints"} <= visible
        assert not [name for name in visible if name.startswith(_WRITE_PREFIXES)]

    def test_admin_sees_writes(self, test_db, operations):
        _org, user, _token = _make_user(test_db, "Admin")
        visible = _visible(operations, resolve_principal(user))

        assert {"create_metric", "update_metric", "create_endpoint", "execute_test_set"} <= visible

    def test_read_only_token_sees_read_tools_only(self, test_db, operations):
        _org, user, _token = _make_user(test_db, "Admin")
        principal = resolve_principal(
            user, scopes=capabilities_for_oauth_scope("read"), kind=AuthKind.TOKEN
        )

        assert _visible(operations, principal) == _read_tools(operations)


@pytest.mark.ee
@pytest.mark.integration
class TestHiddenToolsStillFailAtTheRoute:
    def test_viewer_calling_create_metric_directly_is_refused(self, client, test_db, operations):
        _org, user, token = _make_user(test_db, "Viewer")
        assert "create_metric" not in _visible(operations, resolve_principal(user))

        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                "/metrics/",
                json={"name": "hidden", "evaluation_prompt": "x", "score_type": "binary"},
                headers={"Authorization": f"Bearer {token.token}"},
            )

        assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.text


def _mcp_request(user, **state) -> Request:
    """The HTTP request _MCPApp hands on, after it has authenticated *user*."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"authorization", b"Bearer unused")],
        "state": {"user": user, **state},
    }
    return Request(scope)


def _in_mcp_request(request: Request, coro):
    async def run():
        token = request_ctx.set(
            RequestContext(
                request_id=1, meta=None, session=None, lifespan_context=None, request=request
            )
        )
        try:
            return await coro()
        finally:
            request_ctx.reset(token)

    with _ee_provider_active(), _rbac_enabled():
        return asyncio.run(run())


@pytest.mark.ee
@pytest.mark.integration
class TestMcpServer:
    def _list(self, app, request: Request) -> set[str]:
        server = _create_mcp_server(app)
        handler = server.request_handlers[mcp_types.ListToolsRequest]
        result = _in_mcp_request(
            request, lambda: handler(mcp_types.ListToolsRequest(method="tools/list"))
        )
        return {tool.name for tool in result.root.tools}

    def test_viewer_list_has_no_writes(self, app, test_db):
        _org, user, _token = _make_user(test_db, "Viewer")
        names = self._list(app, _mcp_request(user))

        assert "list_metrics" in names
        assert not [name for name in names if name.startswith(_WRITE_PREFIXES)]

    def test_token_scopes_from_the_request_apply(self, app, test_db, operations):
        _org, user, _token = _make_user(test_db, "Admin")
        request = _mcp_request(
            user,
            **{
                REQUEST_STATE_AUTH_KIND: AuthKind.TOKEN,
                REQUEST_STATE_API_TOKEN_SCOPES: capabilities_for_oauth_scope("read"),
            },
        )

        assert self._list(app, request) == _read_tools(operations)

    def test_calling_a_hidden_tool_says_not_available(self, app, test_db):
        _org, user, _token = _make_user(test_db, "Viewer")
        server = _create_mcp_server(app)
        handler = server.request_handlers[mcp_types.CallToolRequest]
        call = mcp_types.CallToolRequest(
            method="tools/call",
            params=mcp_types.CallToolRequestParams(name="create_metric", arguments={}),
        )

        result = _in_mcp_request(_mcp_request(user), lambda: handler(call))

        body = json.loads(result.root.content[0].text)
        assert body["error"] is True
        assert "not available" in body["detail"]


@pytest.mark.ee
@pytest.mark.integration
class TestArchitectTools:
    """The Architect lists and calls tools as the delegation token's user."""

    def test_viewer_architect_does_not_get_write_tools(self, app, test_db):
        _org, user, _token = _make_user(test_db, "Viewer")
        provider = LocalToolProvider(app, "unused", principal=resolve_principal(user))

        with _ee_provider_active(), _rbac_enabled():
            names = {t["name"] for t in asyncio.run(provider.list_tools())}

        assert "list_metrics" in names
        assert not [name for name in names if name.startswith(_WRITE_PREFIXES)]

    def test_viewer_architect_cannot_call_a_hidden_tool(self, app, test_db):
        _org, user, _token = _make_user(test_db, "Viewer")
        provider = LocalToolProvider(app, "unused", principal=resolve_principal(user))

        with _ee_provider_active(), _rbac_enabled():
            with pytest.raises(ValueError, match="not available"):
                asyncio.run(provider.execute("create_metric", name="x"))
