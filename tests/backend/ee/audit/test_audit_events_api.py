"""Audit log read API: ``/audit-events``.

Rows are inserted straight into ``audit_event`` on the test session, which the
fixture rolls back. Self-audit rows are switched off here and tested in
``test_audit_self_audit.py``.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/audit/test_audit_events_api.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import (
    get_all_capabilities,
    register_capabilities,
)
from rhesis.backend.app.auth.rbac import get_authorization_provider, set_authorization_provider
from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.app.main import app
from rhesis.backend.app.models.base import Base
from rhesis.backend.ee.audit import crud as audit_crud
from rhesis.backend.ee.audit.models import AuditEvent
from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider
from rhesis.backend.events.audit_actions import known_actions
from tests.backend.ee.rbac._rbac_helpers import _assign_org_role
from tests.backend.fixtures.rls import as_org, scope_to_org
from tests.backend.fixtures.test_setup import create_test_organization_and_user

pytestmark = [pytest.mark.ee, pytest.mark.integration]

URL = "/audit-events/"
T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _audit_log_registered():
    # Some suites reset the registry; the gate needs the feature present to grant it.
    register_capabilities(app)
    if not FeatureRegistry.is_registered(FeatureName.AUDIT_LOG):
        FeatureRegistry.register(Feature(name=FeatureName.AUDIT_LOG))


@pytest.fixture(autouse=True)
def _no_lag(monkeypatch):
    # Rows inserted by a test are seconds old at most; the lag has its own test.
    monkeypatch.setattr(audit_crud, "SAFE_LAG_SECONDS", 0.0)


@pytest.fixture(autouse=True)
def _no_self_audit():
    # Each read would add its own audit_log.viewed row to the lists checked here;
    # test_audit_self_audit.py covers those rows.
    with patch("rhesis.backend.ee.audit.router.record_view"):
        yield


class _DenyAuditLog:
    """A licence that covers everything but the audit log, like the team tier."""

    def __init__(self, inner):
        self._inner = inner

    def allows_feature(self, feature, org) -> bool:
        return feature.name != FeatureName.AUDIT_LOG and self._inner.allows_feature(feature, org)

    def info(self, org=None) -> dict:
        return self._inner.info(org)


@contextmanager
def _ee(audit_log_licensed: bool = True):
    """EE RBAC as the decision point; the audit log licensed or not."""
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
        db, f"Audit {role} {suffix}", f"audit_{role.lower()}_{suffix}@rhesis-test.com", role
    )
    org.owner_id = None  # the community owner bypass would hide the role check
    db.flush()
    _assign_org_role(db, org.id, user.id, role)
    db.flush()
    return org, user, token


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _insert(db: Session, org_id, action: str, occurred_at: datetime, trace_id: str = "t1"):
    with as_org(db, org_id):
        return db.execute(
            text(
                "INSERT INTO audit_event (organization_id, occurred_at, action, outcome, "
                "actor_type, channel, ip, trace_id, span_id, changes) "
                "VALUES (CAST(:org AS uuid), :occurred_at, :action, 'success', 'user', 'web', "
                "CAST('203.0.113.7' AS inet), :trace_id, 's1', "
                'CAST(\'[{"field": "name", "kind": "value"}]\' AS jsonb)) RETURNING id'
            ),
            {
                "org": str(org_id),
                "occurred_at": occurred_at,
                "action": action,
                "trace_id": trace_id,
            },
        ).scalar_one()


@pytest.fixture
def admin(test_db):
    """An Admin and five events: three endpoint ones a day apart, then two test_set."""
    org, user, token = _member(test_db, "Admin")
    events = [
        ("endpoint.created", T0),
        ("endpoint.updated", T0 + timedelta(days=1)),
        ("endpoint.deleted", T0 + timedelta(days=2)),
        ("test_set.created", T0 + timedelta(days=3)),
        ("test_set.exported", T0 + timedelta(days=4)),
    ]
    ids = [_insert(test_db, org.id, action, at) for action, at in events]
    # The id, not the row: creating another org expires this one out of reach.
    return org.id, token, ids


def _get(client, token, path: str = URL, **params):
    with _ee():
        return client.get(path, params=params, headers=_auth(token))


class TestList:
    def test_newest_first_with_total(self, client, admin):
        _, token, ids = admin
        resp = _get(client, token)
        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert [e["id"] for e in resp.json()] == [str(i) for i in reversed(ids)]
        assert resp.headers["X-Total-Count"] == "5"
        first = resp.json()[0]
        assert first["ip"] == "203.0.113.7"
        assert first["changes"] == [{"field": "name", "kind": "value"}]
        assert "content_changes" not in first

    def test_filter_on_action_prefix(self, client, admin):
        _, token, _ = admin
        resp = _get(client, token, **{"$filter": "startswith(action,'endpoint.')"})
        assert sorted(e["action"] for e in resp.json()) == [
            "endpoint.created",
            "endpoint.deleted",
            "endpoint.updated",
        ]
        assert resp.headers["X-Total-Count"] == "3"

    def test_filter_on_time_and_action(self, client, admin):
        _, token, _ = admin
        expr = "startswith(action,'endpoint.') and occurred_at ge 2026-10-02T00:00:00Z"
        resp = _get(client, token, **{"$filter": expr})
        assert [e["action"] for e in resp.json()] == ["endpoint.deleted", "endpoint.updated"]

    def test_select(self, client, admin):
        _, token, _ = admin
        resp = _get(client, token, **{"$select": "action,occurred_at"})
        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert set(resp.json()[0]) == {"id", "action", "occurred_at"}
        assert resp.headers["X-Total-Count"] == "5"

    def test_sort_and_page(self, client, admin):
        _, token, _ = admin
        resp = _get(client, token, sort_by="action", sort_order="asc", skip=1, limit=2)
        assert [e["action"] for e in resp.json()] == ["endpoint.deleted", "endpoint.updated"]

    def test_page_size_is_capped(self, client, admin):
        _, token, _ = admin
        assert _get(client, token, limit=101).status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_unknown_sort_field(self, client, admin):
        _, token, _ = admin
        assert _get(client, token, sort_by="nope").status_code == status.HTTP_400_BAD_REQUEST


def _tail(client, token, **params):
    return _get(client, token, sort_by=audit_crud.CURSOR_SORT_FIELD, **params)


class TestCursor:
    def test_walks_every_row_once(self, client, test_db, admin):
        org_id, token, ids = admin
        # Happened earliest, recorded last: the walk follows recorded_at.
        late = _insert(test_db, org_id, "endpoint.updated", T0 - timedelta(days=1))
        recorded = [str(i) for i in ids + [late]]

        for order in ("desc", "asc"):
            seen, cursor = [], None
            while True:
                params = {"limit": 2, "sort_order": order}
                if cursor:
                    params["cursor"] = cursor
                page = _tail(client, token, **params).json()
                if not page:
                    break
                seen += [e["id"] for e in page]
                cursor = page[-1]["id"]
            assert seen == (recorded if order == "asc" else recorded[::-1]), order

    def test_cursor_matches_offset_paging(self, client, admin):
        _, token, _ = admin
        for order in ("desc", "asc"):
            first = _tail(client, token, limit=2, sort_order=order).json()
            by_cursor = _tail(
                client, token, limit=2, sort_order=order, cursor=first[-1]["id"]
            ).json()
            by_offset = _tail(client, token, limit=2, sort_order=order, skip=2).json()
            assert by_cursor == by_offset, order

    @pytest.mark.parametrize("sort_by", [None, "occurred_at", "action"])
    def test_needs_recorded_at_order(self, client, admin, sort_by):
        _, token, ids = admin
        params = {"cursor": str(ids[0])}
        if sort_by:
            params["sort_by"] = sort_by
        resp = _get(client, token, **params)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["detail"] == "cursor needs sort_by=recorded_at"

    def test_unknown_cursor(self, client, admin):
        _, token, _ = admin
        resp = _tail(client, token, cursor=str(uuid.uuid4()))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["detail"] == "Unknown cursor"


class TestTailBound:
    def test_lag_holds_back_recent_rows_only_when_tailing(self, client, admin, monkeypatch):
        monkeypatch.setattr(audit_crud, "SAFE_LAG_SECONDS", 3600.0)
        _, token, ids = admin
        assert _tail(client, token, sort_order="asc").json() == []
        newest = _tail(client, token, sort_order="desc").json()
        assert [e["id"] for e in newest] == [str(i) for i in reversed(ids)]

    def test_open_transaction_holds_back_rows_recorded_after_it_began(self, client, test_db, admin):
        """A row recorded earlier but committed later is never skipped by the cursor."""
        org_id, token, ids = admin
        cursor = str(ids[-1])
        engine = test_db.get_bind().engine

        with engine.connect() as other:
            other.execute(
                text("SELECT set_config('app.current_organization', :org, true)"),
                {"org": str(org_id)},
            )
            early = _insert_on(other, org_id)
            late = _insert(test_db, org_id, "endpoint.updated", T0)

            page = _tail(client, token, sort_order="asc", cursor=cursor).json()
            assert page == [], "the open transaction's start bounds what is safe to read"

            other.commit()

        page = _tail(client, token, sort_order="asc", cursor=cursor).json()
        assert [e["id"] for e in page] == [str(early), str(late)]


def _insert_on(conn, org_id):
    # Committed for real: audit_event is append-only, so the row stays in the worker DB.
    return conn.execute(
        text(
            "INSERT INTO audit_event (organization_id, occurred_at, action, outcome, "
            "actor_type, channel, trace_id, span_id, changes) "
            "VALUES (CAST(:org AS uuid), now(), 'endpoint.created', 'success', 'user', "
            "'web', 't-late', 's1', CAST('[]' AS jsonb)) RETURNING id"
        ),
        {"org": str(org_id)},
    ).scalar_one()


class TestDetail:
    def test_reads_one(self, client, admin):
        _, token, ids = admin
        resp = _get(client, token, f"{URL}{ids[0]}")
        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert resp.json()["action"] == "endpoint.created"

    def test_missing_is_404(self, client, admin):
        _, token, _ = admin
        resp = _get(client, token, f"{URL}{uuid.uuid4()}")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestTenantIsolation:
    def test_other_orgs_events_are_invisible(self, client, test_db, admin):
        org_id, token, ids = admin
        other_org, _, _ = _member(test_db, "Admin")
        foreign = _insert(test_db, other_org.id, "endpoint.created", T0)
        scope_to_org(test_db, org_id)

        listed = {e["id"] for e in _get(client, token, limit=100).json()}
        assert listed == {str(i) for i in ids}
        assert _get(client, token, f"{URL}{foreign}").status_code == status.HTTP_404_NOT_FOUND
        resp = _tail(client, token, cursor=str(foreign))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_rls_hides_rows_even_when_asked_for_another_org(self, test_db, admin):
        """Bound to one org, asking for another's rows by id returns nothing."""
        org_id, _, _ = admin
        other_org, _, _ = _member(test_db, "Admin")
        other_org_id = other_org.id
        foreign = _insert(test_db, other_org_id, "endpoint.created", T0)
        scope_to_org(test_db, org_id)

        assert audit_crud.list_audit_events(test_db, str(other_org_id)) == []
        assert audit_crud.get_audit_event(test_db, foreign, str(other_org_id)) is None


class TestAccess:
    def test_viewer_is_denied(self, client, test_db):
        _, _, token = _member(test_db, "Viewer")
        resp = _get(client, token)
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.headers.get("X-Accepted-Permissions") == "audit_log:read"

    def test_admin_is_allowed(self, client, admin):
        _, token, _ = admin
        assert _get(client, token).status_code == status.HTTP_200_OK

    @pytest.mark.parametrize("path", [URL, f"{URL}actions"])
    def test_unlicensed_org_gets_404(self, client, admin, path):
        _, token, _ = admin
        with _ee(audit_log_licensed=False):
            resp = client.get(path, headers=_auth(token))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_token_scoped_to_audit_log_read_can_list(self, client, test_db, admin):
        _, token, ids = admin
        token.scopes = ["audit_log:read"]
        test_db.flush()
        resp = _get(client, token)
        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert len(resp.json()) == len(ids)

    def test_token_scoped_elsewhere_is_denied(self, client, test_db, admin):
        _, token, _ = admin
        token.scopes = ["test_set:read"]
        test_db.flush()
        assert _get(client, token).status_code == status.HTTP_403_FORBIDDEN


class TestActions:
    def test_matches_known_actions(self, client, admin):
        _, token, _ = admin
        resp = _get(client, token, f"{URL}actions")
        assert resp.status_code == status.HTTP_200_OK, resp.text
        body = resp.json()
        assert [a["action"] for a in body] == sorted(known_actions(get_all_capabilities()))
        assert {"action": "endpoint.updated", "resource": "endpoint", "verb": "updated"} in body
        assert {"action": "session.signed_in", "resource": "session", "verb": "signed_in"} in body


def test_model_is_outside_the_app_registry():
    """Generic code walks Base.registry (recycle bin, /resolve, tenant auto-filter)."""
    assert AuditEvent not in {m.class_ for m in Base.registry.mappers}
