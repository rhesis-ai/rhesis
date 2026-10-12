"""The audit log as MCP tools, for MCP clients and the Architect.

The tools resolve to the ``/audit-events`` routes, so the plan- and
role-aware tool list hides them from orgs without the audit log and from
roles without ``audit_log:read``. The filters the tool descriptions teach
are run here against real rows.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/audit/test_audit_mcp_tools.py -v
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app import dependencies
from rhesis.backend.app.auth.capabilities import get_all_capabilities, register_capabilities
from rhesis.backend.app.auth.principal import resolve_principal
from rhesis.backend.app.auth.rbac import get_authorization_provider, set_authorization_provider
from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.app.main import app
from rhesis.backend.app.mcp_server import tools as mcp_tools
from rhesis.backend.app.mcp_server.local_tools import LocalToolProvider
from rhesis.backend.app.mcp_server.tools import (
    build_tools_and_operations,
    load_tool_configs,
    visible_tools_for,
)
from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider
from rhesis.backend.events.audit_actions import known_actions
from tests.backend.ee.rbac._rbac_helpers import _assign_org_role
from tests.backend.fixtures.rls import as_org
from tests.backend.fixtures.test_setup import create_test_organization_and_user

pytestmark = [pytest.mark.ee, pytest.mark.integration]

AUDIT_TOOLS = {"list_audit_events", "get_audit_event", "list_audit_actions"}


@pytest.fixture(autouse=True)
def _audit_log_registered():
    # Some suites reset the registry; the gate needs the feature present to grant it.
    register_capabilities(app)
    if not FeatureRegistry.is_registered(FeatureName.AUDIT_LOG):
        FeatureRegistry.register(Feature(name=FeatureName.AUDIT_LOG))


@pytest.fixture(autouse=True)
def _tenant_sessions_use_test_db(test_db, monkeypatch):
    """The visibility check opens its own sessions; point them at ``test_db``."""

    @contextmanager
    def _fake(*_args, **_kwargs):
        yield test_db

    monkeypatch.setattr(mcp_tools, "get_db_with_tenant_variables", _fake)
    monkeypatch.setattr(dependencies, "get_db_with_tenant_variables", _fake)


class _DenyAuditLog:
    """A licence that covers everything but the audit log."""

    def __init__(self, inner):
        self._inner = inner

    def allows_feature(self, feature, org) -> bool:
        return feature.name != FeatureName.AUDIT_LOG and self._inner.allows_feature(feature, org)

    def info(self, org=None) -> dict:
        return self._inner.info(org)


@contextmanager
def _ee(audit_log_licensed: bool = True):
    previous = get_authorization_provider()
    set_authorization_provider(PermissionAuthorizationProvider())
    license_ = FeatureRegistry._license
    if not audit_log_licensed:
        license_ = _DenyAuditLog(license_)
    try:
        with (
            patch.object(FeatureRegistry, "_license", license_),
            patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True),
        ):
            yield
    finally:
        set_authorization_provider(previous)


def _member(db: Session, role: str):
    suffix = uuid.uuid4().hex[:8]
    org, user, token = create_test_organization_and_user(
        db, f"Audit tools {role} {suffix}", f"audit_tools_{suffix}@rhesis-test.com", role
    )
    org.owner_id = None  # the community owner bypass would hide the role check
    db.flush()
    _assign_org_role(db, org.id, user.id, role)
    db.commit()
    return org, user, token


@pytest.fixture(scope="module")
def operations():
    _, ops = build_tools_and_operations(app)
    return ops


def _visible(operations, user, licensed: bool = True) -> frozenset[str]:
    with _ee(audit_log_licensed=licensed):
        return visible_tools_for(operations, resolve_principal(user), None)


class TestToolsResolveToTheAuditRoutes:
    def test_each_tool_needs_the_feature_and_audit_log_read(self, operations):
        for name in AUDIT_TOOLS:
            assert operations[name]["feature"] == FeatureName.AUDIT_LOG.value, name
            assert operations[name]["capability"] == "audit_log:read", name

    def test_no_tool_reaches_the_export_or_settings_routes(self, operations):
        audit_ops = [op for op in operations.values() if op["path"].startswith("/audit-events")]
        assert len(audit_ops) == len(AUDIT_TOOLS)
        assert all(op["method"] == "GET" for op in audit_ops)

    def test_resource_names_the_descriptions_teach_are_real(self):
        """list_audit_actions points at these; a rename would send agents to nothing."""
        resources = {a.split(".", 1)[0] for a in known_actions(get_all_capabilities())}
        assert {"member", "project_member", "role", "token", "api_clients"} <= resources
        assert "member.updated" in known_actions(get_all_capabilities())

    def test_the_list_says_how_to_attribute_and_what_empty_means(self):
        description = {tc["name"]: tc for tc in load_tool_configs()}["list_audit_events"][
            "description"
        ].replace("\n", " ")
        assert "Report only the rows this returns" in description
        assert "name them from actor_label" in description
        assert "saying so is the answer" in description


class TestVisibility:
    def test_admin_in_an_entitled_org_sees_the_tools(self, test_db, operations):
        _org, user, _token = _member(test_db, "Admin")
        assert AUDIT_TOOLS <= _visible(operations, user)

    def test_viewer_does_not(self, test_db, operations):
        _org, user, _token = _member(test_db, "Viewer")
        visible = _visible(operations, user)
        assert "list_metrics" in visible
        assert not AUDIT_TOOLS & visible

    def test_admin_in_an_org_without_the_audit_log_does_not(self, test_db, operations):
        _org, user, _token = _member(test_db, "Admin")
        visible = _visible(operations, user, licensed=False)
        assert "create_metric" in visible
        assert not AUDIT_TOOLS & visible

    @pytest.mark.parametrize("role, sees", [("Admin", True), ("Viewer", False)])
    def test_the_architect_gets_the_same_list(self, test_db, role, sees):
        # One org per test: the shared test session is scoped to the last org created.
        _org, user, _token = _member(test_db, role)
        provider = LocalToolProvider(app, "unused", principal=resolve_principal(user))
        with _ee():
            names = {t["name"] for t in asyncio.run(provider.list_tools())}

        assert "list_metrics" in names
        assert (AUDIT_TOOLS <= names) is sees
        assert bool(AUDIT_TOOLS & names) is sees


T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _insert(db: Session, org_id, **row) -> uuid.UUID:
    values = {
        "org": str(org_id),
        "occurred_at": T0,
        "action": "metric.updated",
        "outcome": "success",
        "actor_type": "user",
        "channel": "web",
        "actor_label": "Alice Example <alice@example.com>",
        "resource_id": None,
        "resource_label": None,
        "trace_id": "t1",
        "changes": '[{"field": "threshold", "kind": "value", "before": 0.5, "after": 0.8}]',
        **row,
    }
    with as_org(db, org_id):
        return db.execute(
            text(
                "INSERT INTO audit_event (organization_id, occurred_at, action, outcome, "
                "actor_type, actor_label, channel, resource_id, resource_label, trace_id, "
                "span_id, changes) VALUES (CAST(:org AS uuid), :occurred_at, :action, "
                ":outcome, :actor_type, :actor_label, :channel, CAST(:resource_id AS uuid), "
                ":resource_label, :trace_id, 's1', CAST(:changes AS jsonb)) RETURNING id"
            ),
            values,
        ).scalar_one()


class TestTheArchitectCanAnswerAuditQuestions:
    """Runs list_audit_events the way the Architect does, through the real route."""

    @pytest.fixture
    def admin(self, client, test_db):
        org, user, token = _member(test_db, "Admin")
        metric_id = uuid.uuid4()
        rows = {
            "threshold": _insert(
                test_db,
                org.id,
                resource_id=str(metric_id),
                resource_label="Refusal Detection",
                trace_id="req-1",
            ),
            "by_architect": _insert(
                test_db,
                org.id,
                action="endpoint.updated",
                occurred_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
                channel="architect",
                actor_label="Bob Builder <bob@example.com>",
                resource_label="Support Bot",
                changes='[{"field": "auth_token", "kind": "secret", "before": null, '
                '"after": null}]',
            ),
            "role_change": _insert(
                test_db,
                org.id,
                action="member.updated",
                actor_type="api_token",
                actor_label="Carol Token <carol@example.com>",
                occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            ),
            "failed_sign_in": _insert(
                test_db,
                org.id,
                action="session.signed_in",
                actor_label="Dana Ops <dana@example.com>",
                outcome="failure",
                occurred_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
            ),
            "denied": _insert(
                test_db,
                org.id,
                action="test.deleted",
                actor_label="Dana Ops <dana@example.com>",
                outcome="denied",
                occurred_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
            ),
            "export": _insert(
                test_db,
                org.id,
                action="test_set.exported",
                actor_label="Dana Ops <dana@example.com>",
                occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            ),
        }
        test_db.commit()
        provider = LocalToolProvider(app, token.token, principal=resolve_principal(user))
        return provider, metric_id, rows

    def _list(self, provider, **arguments) -> list[dict]:
        with _ee():
            result = asyncio.run(provider.execute("list_audit_events", **arguments))
        assert result.success, result.error
        return json.loads(result.content)["results"]

    def test_who_changed_a_metric(self, admin):
        provider, metric_id, rows = admin
        (row,) = self._list(provider, filter=f"resource_id eq '{metric_id}'")

        assert row["id"] == str(rows["threshold"])
        assert row["actor_label"] == "Alice Example <alice@example.com>"
        assert row["changes"] == [
            {"field": "threshold", "kind": "value", "before": 0.5, "after": 0.8}
        ]

    @pytest.mark.parametrize(
        "expr, expected",
        [
            ("startswith(action,'metric.')", "threshold"),
            ("contains(tolower(resource_label), 'refusal')", "threshold"),
            ("contains(tolower(actor_label), 'alice')", "threshold"),
            ("trace_id eq 'req-1'", "threshold"),
            ("channel eq 'architect'", "by_architect"),
            ("occurred_at ge 2026-10-01T00:00:00Z and channel eq 'architect'", "by_architect"),
            ("actor_type eq 'api_token'", "role_change"),
            (
                "startswith(action,'member.') or startswith(action,'project_member.') or "
                "startswith(action,'role.') or startswith(action,'token.') or "
                "startswith(action,'api_clients.')",
                "role_change",
            ),
            ("action eq 'session.signed_in' and outcome eq 'failure'", "failed_sign_in"),
            ("outcome eq 'denied'", "denied"),
            ("action eq 'test_set.exported'", "export"),
        ],
    )
    def test_the_filters_the_description_teaches(self, admin, expr, expected):
        provider, _metric_id, rows = admin
        assert [r["id"] for r in self._list(provider, filter=expr)] == [str(rows[expected])]

    def test_the_run_comparison_query(self, admin):
        """result-analysis.md: several resources, between two run timestamps."""
        provider, metric_id, rows = admin
        expr = (
            f"(resource_id eq '{uuid.uuid4()}' or resource_id eq '{metric_id}') "
            "and occurred_at ge 2026-09-30T12:00:00.123456 "
            "and occurred_at le 2026-10-01T23:59:59.999999"
        )
        assert [r["id"] for r in self._list(provider, filter=expr)] == [str(rows["threshold"])]

    def test_newest_first(self, admin):
        provider, _metric_id, rows = admin
        assert [r["id"] for r in self._list(provider)] == [
            str(rows[k])
            for k in (
                "by_architect",
                "threshold",
                "role_change",
                "failed_sign_in",
                "denied",
                "export",
            )
        ]

    def test_a_secret_change_carries_no_values(self, admin):
        provider, _metric_id, _rows = admin
        (row,) = self._list(provider, filter="channel eq 'architect'")
        assert row["changes"] == [
            {"field": "auth_token", "kind": "secret", "before": None, "after": None}
        ]

    def test_nothing_matched_says_so(self, admin):
        provider, _metric_id, _rows = admin
        with _ee():
            result = asyncio.run(
                provider.execute("list_audit_events", filter="startswith(action,'source.')")
            )
        body = json.loads(result.content)
        assert body["results"] == []
        assert "This is the answer" in body["_pagination"]["hint"]

    def test_get_audit_event_reads_one_row(self, admin):
        provider, _metric_id, rows = admin
        with _ee():
            result = asyncio.run(
                provider.execute("get_audit_event", event_id=str(rows["threshold"]))
            )
        assert result.success, result.error
        assert json.loads(result.content)["resource_label"] == "Refusal Detection"
