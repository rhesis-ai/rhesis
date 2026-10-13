"""Explicit audit events: sessions, passwords, denials, exports, token exchanges.

Rows a request writes in its own transaction ride the test's savepoint. Rows
written on the sink's own session (denials, failed sign-ins) really commit,
so those tests use the shared, committed test org. Every test reads only rows
carrying its own request id: the table is append-only.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import text

from rhesis.backend.app import models
from rhesis.backend.app.auth.capabilities import get_all_capabilities, register_capabilities
from rhesis.backend.app.auth.rbac import enforced_capability_for_route
from rhesis.backend.app.auth.token_utils import create_password_reset_token
from rhesis.backend.app.crud.test_set import add_tests_to_test_set
from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.provenance import (
    ActorType,
    Channel,
    RequestProvenance,
    bind_task_provenance,
    reset_task_provenance,
)
from rhesis.backend.app.services import audit_events
from rhesis.backend.app.services.audit_events import denied_action
from rhesis.backend.app.utils.encryption import hash_password
from rhesis.backend.events.audit_actions import known_actions
from tests.backend.ee.sso.token_exchange._helpers import payload as exchange_payload
from tests.backend.fixtures.test_setup import create_test_user

PASSWORD = "a-long-and-unusual-passphrase-42"


def _rows(db, org_id: str, request_id: str) -> list:
    return list(
        db.execute(
            text(
                "SELECT action, outcome, status_code, actor_type, actor_id, actor_label, "
                "actor_credential_id, channel, resource_id, resource_label, project_id "
                "FROM audit_event WHERE organization_id = CAST(:org AS uuid) "
                "AND request_id = :request ORDER BY recorded_at, id"
            ),
            {"org": org_id, "request": request_id},
        ).mappings()
    )


def _request_id() -> str:
    return f"req-{uuid.uuid4().hex}"


def _headers(request_id: str) -> dict:
    return {"X-Request-ID": request_id, "X-Rhesis-Client": "web"}


@pytest.fixture(autouse=True)
def _audit_installed():
    assert FeatureRegistry.is_registered(FeatureName.AUDIT_LOG)


@pytest.fixture
def emitted(monkeypatch) -> list:
    """Every event the explicit-event helpers emit, still delivered to the sinks."""
    seen = []
    real_emit = audit_events.emit

    def _spy(event, db=None):
        seen.append(event)
        real_emit(event, db=db)

    monkeypatch.setattr(audit_events, "emit", _spy)
    return seen


class _FakeRedis:
    """``SET NX`` with no expiry: everything in a test falls inside one window."""

    def __init__(self):
        self.keys: set[str] = set()

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return None
        self.keys.add(key)
        return True

    def delete(self, *keys):
        self.keys.difference_update(keys)


@pytest.fixture
def fresh_window(monkeypatch):
    """An empty repeat window, so earlier tests' denials and refreshes don't suppress rows."""
    monkeypatch.setattr(audit_events._repeats, "_initialized", True)
    monkeypatch.setattr(audit_events._repeats, "_redis", _FakeRedis())


def _bind_provenance(request, request_id: str, actor_id=None) -> None:
    """The ambient provenance a direct call (no HTTP request) records with."""
    token = bind_task_provenance(
        RequestProvenance(
            actor_type=ActorType.USER if actor_id else ActorType.ANONYMOUS,
            actor_id=actor_id,
            credential_id=None,
            credential_hint=None,
            channel=Channel.WEB,
            ip=None,
            user_agent=None,
            request_id=request_id,
        )
    )
    request.addfinalizer(lambda: reset_task_provenance(token))


@pytest.fixture
def member(test_db, test_org_id):
    """A user with a password in the committed test org."""
    user = create_test_user(test_db, test_org_id, f"audit-{uuid.uuid4().hex[:8]}@example.com")
    user.password_hash = hash_password(PASSWORD)
    test_db.flush()
    return user


class TestSignIn:
    def test_success_is_recorded_with_the_user_as_actor(self, client, test_db, test_org_id, member):
        request_id = _request_id()

        response = client.post(
            "/auth/login/email",
            json={"email": member.email, "password": PASSWORD},
            headers=_headers(request_id),
        )

        assert response.status_code == 200, response.text
        # Sign-in may also update the account (e.g. last login), which is captured separately.
        (row,) = [
            r for r in _rows(test_db, test_org_id, request_id) if r["action"] != "member.updated"
        ]
        assert row["action"] == "session.signed_in"
        assert row["outcome"] == "success"
        assert row["actor_type"] == "user"
        assert row["actor_id"] == member.id
        assert member.email in row["actor_label"]
        assert row["channel"] == "web"
        assert row["resource_id"] == member.id

    def test_a_failed_audit_write_does_not_block_the_sign_in(self, client, member, monkeypatch):
        from rhesis.backend.ee.audit import sink

        def _broken(*args, **kwargs):
            raise RuntimeError("audit store unavailable")

        # The sink's own session, which sign-ins write on; row changes keep the request's.
        monkeypatch.setattr(sink, "get_db_with_tenant_variables", _broken)

        response = client.post(
            "/auth/login/email",
            json={"email": member.email, "password": PASSWORD},
            headers=_headers(_request_id()),
        )

        assert response.status_code == 200, response.text

    def test_wrong_password_is_recorded_as_a_failure(self, client, test_db, test_org_id, member):
        request_id = _request_id()

        response = client.post(
            "/auth/login/email",
            json={"email": member.email, "password": "not-the-password"},
            headers=_headers(request_id),
        )

        assert response.status_code == 401
        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "session.signed_in"
        assert row["outcome"] == "failure"
        assert row["status_code"] == 401
        assert row["actor_type"] == "user"
        assert row["actor_id"] == member.id
        assert row["channel"] == "web"

    def test_an_internal_error_is_not_a_failed_sign_in(self, client, member, emitted, monkeypatch):
        from rhesis.backend.app.routers import auth as auth_router

        def _crash(*args, **kwargs):
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(auth_router, "_authenticate_email_user", _crash)

        response = client.post(
            "/auth/login/email",
            json={"email": member.email, "password": PASSWORD},
            headers=_headers(_request_id()),
        )

        assert response.status_code == 401
        assert emitted == []

    def test_unknown_email_writes_nothing(self, client, emitted):
        response = client.post(
            "/auth/login/email",
            json={"email": f"nobody-{uuid.uuid4().hex}@example.com", "password": PASSWORD},
            headers=_headers(_request_id()),
        )

        assert response.status_code == 401
        assert emitted == []


class TestRefresh:
    @pytest.fixture
    def revoked_token(self, test_db, member) -> str:
        from rhesis.backend.app.auth.refresh_token_utils import (
            create_refresh_token,
            revoke_all_for_user,
        )

        token = create_refresh_token(test_db, str(member.id))
        revoke_all_for_user(test_db, str(member.id))
        test_db.flush()
        return token

    def test_a_refused_token_is_recorded_once_a_minute(
        self, client, test_db, test_org_id, member, revoked_token, fresh_window
    ):
        first, second = _request_id(), _request_id()

        for request_id in (first, second):
            response = client.post(
                "/auth/refresh",
                json={"refresh_token": revoked_token},
                headers=_headers(request_id),
            )
            assert response.status_code == 401

        (row,) = _rows(test_db, test_org_id, first)
        assert row["action"] == "session.refreshed"
        assert row["outcome"] == "failure"
        assert row["status_code"] == 401
        assert row["actor_id"] == member.id
        assert _rows(test_db, test_org_id, second) == []

    def test_an_inactive_account_is_recorded(
        self, client, test_db, test_org_id, member, fresh_window
    ):
        from rhesis.backend.app.auth.refresh_token_utils import create_refresh_token

        token = create_refresh_token(test_db, str(member.id))
        member.is_active = False
        test_db.flush()
        request_id = _request_id()

        response = client.post(
            "/auth/refresh", json={"refresh_token": token}, headers=_headers(request_id)
        )

        assert response.status_code == 401
        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "session.refreshed"
        assert row["outcome"] == "failure"

    def test_an_unknown_token_writes_nothing(self, client, emitted, fresh_window):
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": f"not-a-token-{uuid.uuid4().hex}"},
            headers=_headers(_request_id()),
        )

        assert response.status_code == 401
        assert emitted == []


class TestMagicLink:
    def test_a_replayed_link_is_a_failed_sign_in(self, client, test_db, test_org_id, member):
        from rhesis.backend.app.auth.token_utils import create_magic_link_token

        request_id = _request_id()
        with patch(
            "rhesis.backend.app.routers.auth.claim_token_jti",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = client.post(
                "/auth/magic-link/verify",
                json={"token": create_magic_link_token(str(member.id), member.email)},
                headers=_headers(request_id),
            )

        assert response.status_code == 400
        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "session.signed_in"
        assert row["outcome"] == "failure"
        assert row["status_code"] == 400
        assert row["actor_id"] == member.id

    def test_a_replayed_link_for_an_unknown_email_writes_nothing(self, client, emitted):
        from rhesis.backend.app.auth.token_utils import create_magic_link_token

        with patch(
            "rhesis.backend.app.routers.auth.claim_token_jti",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = client.post(
                "/auth/magic-link/verify",
                json={
                    "token": create_magic_link_token(
                        str(uuid.uuid4()), f"nobody-{uuid.uuid4().hex}@example.com"
                    )
                },
                headers=_headers(_request_id()),
            )

        assert response.status_code == 400
        assert emitted == []


class TestSignOut:
    def test_logout_with_a_session_token_is_recorded(self, client, test_db, test_org_id, member):
        from rhesis.backend.app.auth.token_utils import create_session_token

        request_id = _request_id()
        token = create_session_token(member)

        response = client.get(
            "/auth/logout",
            params={"session_token": token},
            headers={**_headers(request_id), "Accept": "application/json"},
        )

        assert response.status_code == 200
        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "session.signed_out"
        assert row["actor_id"] == member.id
        assert row["actor_type"] == "user"

    def test_a_failed_audit_write_does_not_undo_the_logout(self, client, member, monkeypatch):
        from rhesis.backend.app.auth.token_utils import create_session_token
        from rhesis.backend.ee.audit import sink

        def _broken(*args, **kwargs):
            raise RuntimeError("audit store unavailable")

        monkeypatch.setattr(sink, "get_db_with_tenant_variables", _broken)

        response = client.get(
            "/auth/logout",
            params={"session_token": create_session_token(member)},
            headers={**_headers(_request_id()), "Accept": "application/json"},
        )

        assert response.status_code == 200


class TestPasswords:
    def test_change_is_recorded(self, client, test_db, test_org_id, member):
        from rhesis.backend.app.auth.token_utils import create_session_token

        request_id = _request_id()
        response = client.post(
            "/auth/change-password",
            json={"current_password": PASSWORD, "new_password": f"{PASSWORD}-new"},
            headers={
                **_headers(request_id),
                "Authorization": f"Bearer {create_session_token(member)}",
            },
        )

        assert response.status_code == 200, response.text
        actions = {r["action"] for r in _rows(test_db, test_org_id, request_id)}
        # The hash change itself is captured as a row change too, value withheld.
        assert actions == {"member.updated", "password.changed"}

    def test_reset_is_recorded(self, client, test_db, test_org_id, member):
        request_id = _request_id()
        with patch(
            "rhesis.backend.app.routers.auth.claim_token_jti",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = client.post(
                "/auth/reset-password",
                json={
                    "token": create_password_reset_token(str(member.id), member.email),
                    "new_password": f"{PASSWORD}-reset",
                },
                headers=_headers(request_id),
            )

        assert response.status_code == 200, response.text
        rows = _rows(test_db, test_org_id, request_id)
        reset = next(r for r in rows if r["action"] == "password.reset")
        assert reset["actor_id"] == member.id
        assert reset["actor_type"] == "user"


class TestDenials:
    @pytest.fixture
    def deny_everything(self, monkeypatch):
        monkeypatch.setattr("rhesis.backend.app.auth.rbac.authorize", lambda *a, **kw: False)

    def test_denied_change_leaves_a_row_although_the_request_rolled_back(
        self, authenticated_client, deny_everything, test_db, test_org_id, authenticated_user_id
    ):
        request_id = _request_id()
        name = f"Denied {uuid.uuid4().hex}"

        response = authenticated_client.post(
            "/test_sets/", json={"name": name}, headers=_headers(request_id)
        )

        assert response.status_code == 403
        assert test_db.query(models.TestSet).filter(models.TestSet.name == name).first() is None
        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "test_set.created"
        assert row["outcome"] == "denied"
        assert row["status_code"] == 403
        assert row["actor_type"] == "api_token"
        assert str(row["actor_id"]) == authenticated_user_id
        assert row["actor_credential_id"]
        assert row["actor_label"]

    def test_denied_read_is_recorded_once_a_minute(
        self, authenticated_client, deny_everything, fresh_window, test_db, test_org_id
    ):
        first, second = _request_id(), _request_id()

        assert authenticated_client.get("/test_sets/", headers=_headers(first)).status_code == 403
        assert authenticated_client.get("/test_sets/", headers=_headers(second)).status_code == 403

        (row,) = _rows(test_db, test_org_id, first)
        assert row["action"] == "test_set.viewed"
        assert row["outcome"] == "denied"
        assert row["status_code"] == 403
        assert _rows(test_db, test_org_id, second) == []

    def test_denied_changes_are_each_recorded(
        self, authenticated_client, deny_everything, fresh_window, test_db, test_org_id
    ):
        request_ids = [_request_id(), _request_id()]
        for request_id in request_ids:
            response = authenticated_client.post(
                "/test_sets/", json={"name": "Denied"}, headers=_headers(request_id)
            )
            assert response.status_code == 403

        for request_id in request_ids:
            (row,) = _rows(test_db, test_org_id, request_id)
            assert row["action"] == "test_set.created"

    def test_an_object_level_denial_in_a_handler_is_recorded(
        self, authenticated_client, test_db, test_org_id, member
    ):
        comment = models.Comment(
            content="Someone else's",
            entity_id=uuid.uuid4(),
            entity_type="Test",
            organization_id=test_org_id,
            user_id=member.id,
        )
        test_db.add(comment)
        test_db.flush()
        request_id = _request_id()

        response = authenticated_client.put(
            f"/comments/{comment.id}", json={"content": "Edited"}, headers=_headers(request_id)
        )

        assert response.status_code == 403, response.text
        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "comment.updated"
        assert row["outcome"] == "denied"
        assert row["status_code"] == 403

    def test_a_denied_profile_edit_is_recorded(
        self, authenticated_client, test_db, test_org_id, member, monkeypatch
    ):
        monkeypatch.setattr("rhesis.backend.app.routers.user.authorize", lambda *a, **kw: False)
        request_id = _request_id()

        response = authenticated_client.put(
            f"/users/{member.id}", json={"name": "Renamed"}, headers=_headers(request_id)
        )

        assert response.status_code == 403, response.text
        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "member.updated"
        assert row["outcome"] == "denied"

    def test_sso_for_another_org_is_recorded_in_the_callers_org(
        self, test_db, test_org_id, member, request
    ):
        from fastapi import HTTPException

        from rhesis.backend.ee.sso.router import _check_org_admin

        request_id = _request_id()
        _bind_provenance(request, request_id, actor_id=str(member.id))

        with pytest.raises(HTTPException) as denied:
            _check_org_admin(member, SimpleNamespace(method="PUT"), str(uuid.uuid4()), test_db)

        assert denied.value.status_code == 403
        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "sso.updated"
        assert row["outcome"] == "denied"
        assert row["actor_id"] == member.id

    def test_a_failure_to_record_never_replaces_the_403(self, caplog):
        # Best effort (S1): a user object missing fields must not turn the 403 into a 500.
        user = SimpleNamespace(id=uuid.uuid4(), organization_id=uuid.uuid4())
        with patch.object(audit_events, "audit_registered", return_value=True):
            audit_events.record_denial("test_set:read", "POST", user)
        assert "Could not record a denied POST test_set:read" in caplog.text

    def test_a_bundle_capability_names_the_http_verb(self):
        assert denied_action("sso:manage", "PUT") == "sso.updated"
        assert denied_action("test_set:execute", "POST") == "test_set.executed"
        assert denied_action("comment:update:own", "PUT") == "comment.updated"

    def test_every_route_denial_has_a_known_action(self):
        from rhesis.backend.app.main import app

        register_capabilities(app)
        known = known_actions(get_all_capabilities())
        unknown = set()
        for route in app.router.routes:
            if not isinstance(route, APIRoute):
                continue
            capability = enforced_capability_for_route(route)
            if capability is None:
                continue
            for method in route.methods & {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                action = denied_action(capability, method)
                if action not in known:
                    unknown.add(f"{method} {route.path}: {action}")
        assert not unknown, sorted(unknown)


class TestExport:
    def test_download_records_test_set_exported(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        prompt = models.Prompt(
            content="What is 2 + 2?", organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add(prompt)
        test_db.flush()
        test = models.Test(
            prompt_id=prompt.id, organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_set = models.TestSet(
            name="Exported set", organization_id=test_org_id, user_id=authenticated_user_id
        )
        test_db.add_all([test, test_set])
        test_db.flush()
        add_tests_to_test_set(test_db, test_set.id, [test.id], test_org_id, authenticated_user_id)
        request_id = _request_id()

        response = authenticated_client.get(
            f"/test_sets/{test_set.id}/download", headers=_headers(request_id)
        )

        assert response.status_code == 200, response.text
        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "test_set.exported"
        assert row["resource_id"] == test_set.id
        assert row["resource_label"] == "Exported set"
        assert row["actor_type"] == "api_token"
        assert str(row["actor_id"]) == authenticated_user_id


class TestTokenExchange:
    def test_rejection_in_a_known_org_is_recorded(self, client, test_db, test_org_id, monkeypatch):
        org = test_db.get(models.Organization, uuid.UUID(test_org_id))
        org.slug = f"audit-{uuid.uuid4().hex[:12]}"
        test_db.flush()
        request_id = _request_id()

        response = client.post(
            "/auth/token-exchange",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token": "header.body.sig",
                "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "audience": f"rhesis:org:{org.slug}",
                "client_id": "brain-prod",
                "client_secret": "wrong",
            },
            headers=_headers(request_id),
        )

        assert response.status_code == 400
        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "token.exchanged"
        assert row["outcome"] == "failure"
        assert row["status_code"] == 400
        assert row["actor_type"] == "anonymous"
        assert row["actor_id"] is None
        assert row["actor_credential_id"] == "brain-prod"

    def test_success_is_recorded_for_the_subject_through_the_client(
        self, test_db, test_org_id, member, monkeypatch, request
    ):
        from rhesis.backend.ee.sso.token_exchange import exchange

        request_id = _request_id()
        # The row goes on the sink's own session, which reads the ambient provenance.
        token = bind_task_provenance(
            RequestProvenance(
                actor_type=ActorType.ANONYMOUS,
                actor_id=None,
                credential_id=None,
                credential_hint=None,
                channel=Channel.API,
                ip=None,
                user_agent=None,
                request_id=request_id,
            )
        )
        request.addfinalizer(lambda: reset_task_provenance(token))
        monkeypatch.setattr(exchange, "_resolve_user", lambda *a, **kw: member)
        monkeypatch.setattr(exchange, "create_session_token", lambda *a, **kw: "jwt")
        resolved = exchange._ResolvedClient(
            org=SimpleNamespace(id=uuid.UUID(test_org_id)),
            auth_client=MagicMock(
                client_id="brain-prod",
                allowed_scopes=["openid"],
                default_scope="openid",
                token_epoch=datetime.now(timezone.utc),
            ),
            sso_config=SimpleNamespace(issuer_url="https://idp.example.com"),
            org_id=test_org_id,
            expected_subject_azp="brain",
            expected_subject_audience="rhesis",
        )

        exchange._complete_exchange(
            test_db, exchange_payload(), resolved, {}, None, None, deny=None
        )

        (row,) = _rows(test_db, test_org_id, request_id)
        assert row["action"] == "token.exchanged"
        assert row["outcome"] == "success"
        assert row["actor_type"] == "api_client"
        assert row["actor_id"] == member.id
        assert row["actor_credential_id"] == "brain-prod"
        assert row["channel"] == "api"

    def test_a_failed_audit_write_does_not_block_the_exchange(
        self, test_db, test_org_id, member, monkeypatch
    ):
        from rhesis.backend.ee.audit import sink
        from rhesis.backend.ee.sso.token_exchange import exchange

        def _broken(*args, **kwargs):
            raise RuntimeError("audit store unavailable")

        monkeypatch.setattr(sink, "get_db_with_tenant_variables", _broken)
        monkeypatch.setattr(exchange, "_resolve_user", lambda *a, **kw: member)
        monkeypatch.setattr(exchange, "create_session_token", lambda *a, **kw: "jwt")
        resolved = exchange._ResolvedClient(
            org=SimpleNamespace(id=uuid.UUID(test_org_id)),
            auth_client=MagicMock(
                client_id="brain-prod",
                allowed_scopes=["openid"],
                default_scope="openid",
                token_epoch=datetime.now(timezone.utc),
            ),
            sso_config=SimpleNamespace(issuer_url="https://idp.example.com"),
            org_id=test_org_id,
            expected_subject_azp="brain",
            expected_subject_audience="rhesis",
        )

        outcome = exchange._complete_exchange(
            test_db, exchange_payload(), resolved, {}, None, None, deny=None
        )

        assert outcome.access_token == "jwt"


class TestApiClientLifecycle:
    """Lifecycle needs no explicit event: change capture already records it."""

    def test_create_and_rotate_are_row_changes(self, test_db, test_org_id, authenticated_user_id):
        from rhesis.backend.ee.api_clients.crud import create_auth_client

        request_id = _request_id()
        test_db.info["_provenance"] = RequestProvenance(
            actor_type=ActorType.USER,
            actor_id=authenticated_user_id,
            credential_id=None,
            credential_hint=None,
            channel=Channel.WEB,
            ip=None,
            user_agent=None,
            request_id=request_id,
        )

        client = create_auth_client(
            test_db,
            organization_id=uuid.UUID(test_org_id),
            client_id=f"audit-{uuid.uuid4().hex[:8]}",
            client_secret_hash="sha256:" + "0" * 64,
            expected_subject_azp="brain",
            allowed_scopes=["openid"],
            default_scope="openid",
        )
        client.client_secret_hash = "sha256:" + "1" * 64
        test_db.flush()

        created, rotated = _rows(test_db, test_org_id, request_id)
        assert created["action"] == "api_clients.created"
        assert rotated["action"] == "api_clients.updated"
        changes = test_db.execute(
            text(
                "SELECT changes FROM audit_event WHERE request_id = :r "
                "AND action = 'api_clients.updated'"
            ),
            {"r": request_id},
        ).scalar()
        assert [(c["field"], c["kind"]) for c in changes] == [("client_secret_hash", "secret")]
        assert "sha256" not in str(changes)
