"""Audit log streaming: ``ee/audit/streaming``.

Delivery runs on the test session (``run_destination``), with DNS and the wire
replaced by ``fake_receiver``. Rows go straight into ``audit_event``; the
fixture rolls them back, except in the two tests that need a second connection
to see a real commit.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/audit/test_audit_streaming.py -v
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import status
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import register_capabilities
from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.app.main import app
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.app.utils import webhooks
from rhesis.backend.ee.audit.streaming import adapters, crud, service
from rhesis.backend.ee.audit.streaming.adapters import Batch, DeliveryError
from rhesis.backend.ee.audit.streaming.models import AuditDestination
from tests.backend.ee.audit.test_audit_events_api import _auth, _ee, _insert, _member
from tests.backend.fixtures.rls import as_org, scope_to_org
from tests.backend.utils.webhook_receiver import fake_receiver

pytestmark = [pytest.mark.ee, pytest.mark.integration]

URL = "/audit-destinations/"
HOOK = "https://hooks.example.com/rhesis"
T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
# Fixed, so every xdist worker collects the same parametrized ids.
SOME_ID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture(autouse=True)
def _audit_log_registered():
    # Some suites reset the registry; the gate needs the feature present to grant it.
    register_capabilities(app)
    if not FeatureRegistry.is_registered(FeatureName.AUDIT_LOG):
        FeatureRegistry.register(Feature(name=FeatureName.AUDIT_LOG))


@pytest.fixture(autouse=True)
def _no_lag(monkeypatch):
    # Rows inserted by a test are seconds old at most; the lag has its own test.
    monkeypatch.setattr(service, "LAG_SECONDS", 0.0)


@pytest.fixture
def admin(test_db):
    org, _, token = _member(test_db, "Admin")
    return org.id, token


def _destination(db: Session, org_id, kind="webhook", config=None, **fields) -> AuditDestination:
    config = config or {"url": HOOK, "secret": webhooks.generate_secret()}
    with as_org(db, org_id):
        values = {
            "organization_id": org_id,
            "name": f"{kind} destination",
            "kind": kind,
            "config": json.dumps(config),
            "cursor_recorded_at": crud.transaction_start(db),
            "cursor_id": uuid.UUID(int=0),
            "consecutive_failures": 0,
            **fields,
        }
        return crud.create_destination(db, AuditDestination(**values))


def _events(db: Session, org_id, count: int) -> list[str]:
    return [
        str(_insert(db, org_id, "endpoint.updated", T0 + timedelta(minutes=i)))
        for i in range(count)
    ]


def _run(db: Session, org_id, destination: AuditDestination) -> None:
    with as_org(db, org_id):
        service.run_destination(db, destination.id)
        db.refresh(destination)


def _sent_ids(requests) -> list[str]:
    return [e["id"] for r in requests for e in json.loads(r.content)["data"]]


class TestDelivery:
    def test_sends_new_events_in_order_and_moves_the_cursor(self, test_db, admin):
        org_id, _ = admin
        destination = _destination(test_db, org_id)
        ids = _events(test_db, org_id, 3)

        with fake_receiver() as received:
            _run(test_db, org_id, destination)

        assert _sent_ids(received) == ids
        assert str(destination.cursor_id) == ids[-1]
        assert destination.last_success_at is not None
        assert destination.consecutive_failures == 0

        with fake_receiver() as received:
            _run(test_db, org_id, destination)
        assert received == []

    def test_sends_events_exactly_as_the_read_api_lists_them(self, client, test_db, admin):
        org_id, token = admin
        destination = _destination(test_db, org_id)
        (event_id,) = _events(test_db, org_id, 1)

        with fake_receiver() as received:
            _run(test_db, org_id, destination)

        with _ee(), patch("rhesis.backend.ee.audit.router.record_view"):
            listed = client.get("/audit-events/", headers=_auth(token)).json()
        assert json.loads(received[0].content)["data"] == [e for e in listed if e["id"] == event_id]
        assert "content_changes" not in json.loads(received[0].content)["data"][0]

    def test_failure_keeps_the_cursor_and_retries_the_same_events(self, test_db, admin):
        org_id, _ = admin
        destination = _destination(test_db, org_id)
        start = destination.cursor_id
        ids = _events(test_db, org_id, 2)

        with fake_receiver(status=503) as failed:
            _run(test_db, org_id, destination)
        assert destination.cursor_id == start
        assert destination.consecutive_failures == 1
        assert destination.last_error.startswith("HTTP 503")
        assert destination.next_attempt_at > datetime.now(timezone.utc)

        with fake_receiver() as received:
            _run(test_db, org_id, destination)
        assert received == [], "still backing off"

        destination.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        test_db.flush()
        with fake_receiver() as received:
            _run(test_db, org_id, destination)

        assert _sent_ids(received) == _sent_ids(failed) == ids
        assert received[0].headers["webhook-id"] == failed[0].headers["webhook-id"]
        assert str(destination.cursor_id) == ids[-1]
        assert destination.consecutive_failures == 0
        assert destination.next_attempt_at is None

    def test_a_bug_in_an_adapter_is_a_failure_without_its_details(self, test_db, admin):
        org_id, _ = admin
        destination = _destination(test_db, org_id, config={"secret": "no url"})
        _events(test_db, org_id, 1)

        _run(test_db, org_id, destination)
        assert destination.last_error == "Unexpected error (KeyError)"
        assert destination.cursor_id == uuid.UUID(int=0)

    def test_sends_in_batches_and_stops_after_the_run_limit(self, test_db, admin, monkeypatch):
        monkeypatch.setattr(service, "BATCH_SIZE", 2)
        monkeypatch.setattr(service, "MAX_BATCHES_PER_RUN", 2)
        org_id, _ = admin
        destination = _destination(test_db, org_id)
        ids = _events(test_db, org_id, 5)

        with fake_receiver() as received:
            _run(test_db, org_id, destination)
        assert [len(json.loads(r.content)["data"]) for r in received] == [2, 2]
        assert str(destination.cursor_id) == ids[3]

        with fake_receiver() as received:
            _run(test_db, org_id, destination)
        assert _sent_ids(received) == ids[4:]

    def test_skips_other_orgs_events(self, test_db, admin):
        org_id, _ = admin
        destination = _destination(test_db, org_id)
        other_org, _, _ = _member(test_db, "Admin")
        _events(test_db, other_org.id, 1)
        ids = _events(test_db, org_id, 1)

        with fake_receiver() as received:
            _run(test_db, org_id, destination)
        assert _sent_ids(received) == ids

    def test_paused_destination_sends_nothing(self, test_db, admin):
        org_id, _ = admin
        destination = _destination(test_db, org_id, paused=True, paused_reason="manual")
        _events(test_db, org_id, 1)

        with fake_receiver() as received:
            _run(test_db, org_id, destination)
        assert received == []

    def test_a_destination_another_run_holds_is_skipped(self, real_commit_test_db, test_org_id):
        """Overlapping runs never deliver the same destination at once."""
        db = real_commit_test_db
        destination_id = _destination(db, uuid.UUID(test_org_id)).id
        db.commit()
        try:
            with db.get_bind().connect() as other:
                other.execute(
                    text("SELECT set_config('app.current_organization', :org, true)"),
                    {"org": test_org_id},
                )
                other.execute(
                    text("SELECT 1 FROM audit_destination WHERE id = :id FOR UPDATE"),
                    {"id": destination_id},
                )
                scope_to_org(db, test_org_id)
                assert crud.lock_due_destination(db, destination_id) is None
                db.rollback()
            # Each transaction may take another pooled connection; scope it again.
            scope_to_org(db, test_org_id)
            assert crud.lock_due_destination(db, destination_id) is not None
        finally:
            db.rollback()
            scope_to_org(db, test_org_id)
            crud.delete_destination(db, crud.get_destination(db, destination_id))
            db.commit()


class TestSafeBound:
    def test_lag_holds_back_recent_rows(self, test_db, admin, monkeypatch):
        monkeypatch.setattr(service, "LAG_SECONDS", 3600.0)
        org_id, _ = admin
        destination = _destination(test_db, org_id)
        _events(test_db, org_id, 1)

        with fake_receiver() as received:
            _run(test_db, org_id, destination)
        assert received == []

    def test_open_transaction_holds_back_rows_recorded_after_it_began(self, test_db, admin):
        """A row recorded earlier but committed later is never skipped by the cursor."""
        org_id, _ = admin
        destination = _destination(test_db, org_id)
        engine = test_db.get_bind().engine

        with engine.connect() as other:
            other.execute(
                text("SELECT set_config('app.current_organization', :org, true)"),
                {"org": str(org_id)},
            )
            early = _insert_on(other, org_id)
            late = _events(test_db, org_id, 1)[0]

            with fake_receiver() as received:
                _run(test_db, org_id, destination)
            assert received == [], "the open transaction's start bounds what is safe to send"

            other.commit()

        with fake_receiver() as received:
            _run(test_db, org_id, destination)
        assert _sent_ids(received) == [str(early), late]


def _insert_on(conn, org_id):
    return conn.execute(
        text(
            "INSERT INTO audit_event (organization_id, occurred_at, action, outcome, "
            "actor_type, channel, trace_id, span_id, changes) "
            "VALUES (CAST(:org AS uuid), now(), 'endpoint.created', 'success', 'user', "
            "'web', 't-late', 's1', CAST('[]' AS jsonb)) RETURNING id"
        ),
        {"org": str(org_id)},
    ).scalar_one()


class TestBackoffAndPause:
    @pytest.mark.parametrize(
        ("failures", "seconds"), [(1, 30), (2, 60), (3, 120), (7, 1920), (8, 3600), (19, 3600)]
    )
    def test_backoff_doubles_up_to_an_hour(self, failures, seconds):
        assert service.backoff(failures) == timedelta(seconds=seconds)

    def test_pauses_itself_after_repeated_failures(self, test_db, admin):
        org_id, _ = admin
        destination = _destination(
            test_db, org_id, consecutive_failures=service.AUTO_PAUSE_AFTER - 1
        )
        _events(test_db, org_id, 1)

        with fake_receiver(status=500):
            _run(test_db, org_id, destination)

        assert destination.paused is True
        assert destination.paused_reason == service.PAUSED_FAILURES
        assert destination.consecutive_failures == service.AUTO_PAUSE_AFTER
        with as_org(test_db, org_id):
            assert destination.id not in crud.due_destination_ids(test_db)

    def test_resuming_starts_again_from_the_cursor(self, test_db, admin):
        org_id, _ = admin
        destination = _destination(
            test_db,
            org_id,
            paused=True,
            paused_reason=service.PAUSED_FAILURES,
            consecutive_failures=service.AUTO_PAUSE_AFTER,
        )
        ids = _events(test_db, org_id, 2)

        service.set_paused(destination, False)
        test_db.flush()
        assert destination.consecutive_failures == 0
        assert destination.paused_reason is None
        with fake_receiver() as received:
            _run(test_db, org_id, destination)
        assert _sent_ids(received) == ids


class TestDeliverAll:
    def test_runs_entitled_orgs_and_survives_one_failing(self, test_db, admin):
        org_id, _ = admin
        destination = _destination(test_db, org_id)
        ids = _events(test_db, org_id, 1)
        broken = str(uuid.uuid4())

        @contextmanager
        def session_for(organization_id):
            if organization_id == broken:
                raise RuntimeError("database unavailable")
            with as_org(test_db, organization_id):
                yield test_db

        with (
            patch.object(service, "_entitled_organization_ids", return_value=[broken, str(org_id)]),
            patch.object(service, "get_db_with_tenant_variables", session_for),
            fake_receiver() as received,
        ):
            service.deliver_all()

        assert _sent_ids(received) == ids
        test_db.refresh(destination)
        assert str(destination.cursor_id) == ids[-1]

    def test_lists_only_entitled_orgs(self, test_db, admin):
        org_id, _ = admin
        with patch.object(service, "SessionLocal", return_value=nullcontext(test_db)):
            with _ee():
                assert str(org_id) in service._entitled_organization_ids()
            with _ee(audit_log_licensed=False):
                assert str(org_id) not in service._entitled_organization_ids()


def _batch(*events) -> Batch:
    return Batch("org-1", "dest-1", list(events))


_EVENT = {
    "id": "0192f0c4-0000-7000-8000-000000000001",
    "action": "endpoint.updated",
    "occurred_at": "2026-10-01T12:00:00Z",
    "recorded_at": "2026-10-01T12:00:01Z",
}
_LATER = {
    **_EVENT,
    "id": "0192f0c4-0000-7000-8000-000000000002",
    "recorded_at": "2026-10-02T00:00:01Z",
}


class TestAdapters:
    def test_webhook_is_a_signed_standard_webhook(self):
        secret = webhooks.generate_secret()
        with fake_receiver() as received:
            adapters.send_webhook({"url": HOOK, "secret": secret}, _batch(_EVENT))
        (request,) = received
        assert str(request.url) == HOOK
        assert json.loads(request.content)["type"] == "audit_log.events"
        assert json.loads(request.content)["data"] == [_EVENT]
        headers = request.headers
        assert headers["webhook-id"].startswith("msg_")
        assert headers["webhook-signature"] == webhooks.sign(
            secret, headers["webhook-id"], int(headers["webhook-timestamp"]), request.content
        )

    def test_splunk_hec(self):
        config = {"url": "https://splunk.example.com:8088/services/collector/event", "token": "t0k"}
        with fake_receiver() as received:
            adapters.send_splunk_hec(config, _batch(_EVENT, _LATER))
        (request,) = received
        assert str(request.url) == config["url"]
        assert request.headers["authorization"] == "Splunk t0k"
        lines = [json.loads(line) for line in request.content.splitlines()]
        assert lines[0] == {
            "time": T0.timestamp(),
            "source": "rhesis",
            "sourcetype": "rhesis:audit",
            "event": _EVENT,
        }
        assert [line["event"] for line in lines] == [_EVENT, _LATER]

    def test_datadog(self):
        with fake_receiver() as received:
            adapters.send_datadog({"site": "datadoghq.eu", "api_key": "k3y"}, _batch(_EVENT))
        (request,) = received
        assert str(request.url) == "https://http-intake.logs.datadoghq.eu/api/v2/logs"
        assert request.headers["dd-api-key"] == "k3y"
        assert json.loads(request.content) == [
            {
                "ddsource": "rhesis",
                "service": "rhesis-audit-log",
                "message": "endpoint.updated",
                "date": "2026-10-01T12:00:00Z",
                "audit_event": _EVENT,
            }
        ]

    def test_a_redirect_is_a_failure(self):
        with fake_receiver(status=307, location="https://elsewhere.example.com/") as received:
            with pytest.raises(DeliveryError, match="HTTP 307"):
                adapters.send_webhook(
                    {"url": HOOK, "secret": webhooks.generate_secret()}, _batch(_EVENT)
                )
        assert len(received) == 1

    def test_internal_address_at_send_time_is_a_failure(self):
        with fake_receiver(addresses={"hooks.example.com": "169.254.169.254"}) as received:
            with pytest.raises(DeliveryError, match="SSRFError"):
                adapters.send_webhook(
                    {"url": HOOK, "secret": webhooks.generate_secret()}, _batch(_EVENT)
                )
        assert received == []


def _call(client, token, method: str, path: str = URL, **kwargs):
    with _ee():
        return client.request(method, path, headers=_auth(token), **kwargs)


class TestApi:
    def test_add_a_webhook_returns_its_secret_once(self, client, admin):
        _, token = admin
        with fake_receiver():
            resp = _call(
                client, token, "POST", json={"kind": "webhook", "name": "SIEM", "url": HOOK}
            )
        assert resp.status_code == status.HTTP_201_CREATED, resp.text
        created = resp.json()
        assert created["signing_secret"].startswith("whsec_")
        assert created["settings"] == {"url": HOOK}
        assert created["paused"] is False

        listed = _call(client, token, "GET").json()
        assert [d["id"] for d in listed] == [created["id"]]
        assert "signing_secret" not in listed[0]
        assert created["signing_secret"] not in json.dumps(listed)

    @pytest.mark.parametrize(
        ("payload", "secret"),
        [
            (
                {
                    "kind": "splunk_hec",
                    "name": "Splunk",
                    "url": "https://splunk.example.com/services/collector/event",
                    "token": "hec-secret",
                },
                "hec-secret",
            ),
            (
                {"kind": "datadog", "name": "DD", "site": "datadoghq.com", "api_key": "dd-secret"},
                "dd-secret",
            ),
        ],
    )
    def test_secrets_are_never_returned_and_stored_encrypted(
        self, client, test_db, admin, payload, secret
    ):
        org_id, token = admin
        with fake_receiver():
            resp = _call(client, token, "POST", json=payload)
        assert resp.status_code == status.HTTP_201_CREATED, resp.text
        assert secret not in resp.text
        assert secret not in _call(client, token, "GET", f"{URL}{resp.json()['id']}").text
        with as_org(test_db, org_id):
            stored = test_db.execute(
                text("SELECT config FROM audit_destination WHERE id = CAST(:id AS uuid)"),
                {"id": resp.json()["id"]},
            ).scalar_one()
        assert secret not in stored

    @pytest.mark.parametrize(
        ("url", "ip"),
        [
            ("https://hooks.example.com/x", "10.1.2.3"),
            ("https://hooks.example.com/x", "127.0.0.1"),
            ("https://hooks.example.com/x", "169.254.169.254"),
            ("http://hooks.example.com/x", "93.184.216.34"),
        ],
    )
    def test_refuses_internal_and_plain_http_urls(self, client, admin, url, ip):
        _, token = admin
        with fake_receiver(addresses={"hooks.example.com": ip}):
            resp = _call(client, token, "POST", json={"kind": "webhook", "name": "x", "url": url})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert _call(client, token, "GET").json() == []

    def test_unknown_kind_is_rejected(self, client, admin):
        _, token = admin
        resp = _call(client, token, "POST", json={"kind": "storage", "name": "Archive"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_pause_resume_and_delete(self, client, admin):
        _, token = admin
        with fake_receiver():
            created = _call(
                client, token, "POST", json={"kind": "webhook", "name": "x", "url": HOOK}
            )
        path = f"{URL}{created.json()['id']}"

        paused = _call(client, token, "PATCH", path, json={"paused": True}).json()
        assert (paused["paused"], paused["paused_reason"]) == (True, "manual")
        resumed = _call(client, token, "PATCH", path, json={"paused": False}).json()
        assert (resumed["paused"], resumed["paused_reason"]) == (False, None)

        assert _call(client, token, "DELETE", path).status_code == status.HTTP_204_NO_CONTENT
        assert _call(client, token, "GET", path).status_code == status.HTTP_404_NOT_FOUND

    def test_send_a_test_event(self, client, admin):
        _, token = admin
        with fake_receiver():
            created = _call(
                client, token, "POST", json={"kind": "webhook", "name": "x", "url": HOOK}
            )
        path = f"{URL}{created.json()['id']}/test"

        with fake_receiver() as received:
            ok = _call(client, token, "POST", path).json()
        assert ok == {"delivered": True, "error": None}
        body = json.loads(received[0].content)
        assert body["type"] == "audit_log.test"
        assert body["data"][0]["action"] == "audit_log.test"

        with fake_receiver(status=401):
            failed = _call(client, token, "POST", path).json()
        assert failed["delivered"] is False
        assert failed["error"].startswith("HTTP 401")
        after = _call(client, token, "GET", f"{URL}{created.json()['id']}").json()
        assert after["delivered_through"] == created.json()["delivered_through"]
        assert after["consecutive_failures"] == 0

    def test_changes_to_destinations_are_audited(self, client, test_db, admin):
        org_id, token = admin
        with fake_receiver():
            created = _call(
                client, token, "POST", json={"kind": "webhook", "name": "x", "url": HOOK}
            )
        _call(client, token, "PATCH", f"{URL}{created.json()['id']}", json={"paused": True})
        with as_org(test_db, org_id):
            rows = test_db.execute(
                text(
                    "SELECT action, changes FROM audit_event WHERE resource_id = CAST(:id AS uuid) "
                    "ORDER BY recorded_at"
                ),
                {"id": created.json()["id"]},
            ).all()
        assert [r.action for r in rows] == [
            "audit_destination.created",
            "audit_destination.updated",
        ]
        assert {"field": "config", "kind": "secret"} in [
            {k: c[k] for k in ("field", "kind")} for c in rows[0].changes
        ]
        assert {c["field"] for c in rows[1].changes} == {"paused", "paused_reason"}


class TestAccess:
    def test_viewer_is_denied(self, client, test_db):
        _, _, token = _member(test_db, "Viewer")
        resp = _call(client, token, "GET")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.headers.get("X-Accepted-Permissions") == "audit_log:manage"

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("POST", URL),
            ("GET", f"{URL}{SOME_ID}"),
            ("PATCH", f"{URL}{SOME_ID}"),
            ("DELETE", f"{URL}{SOME_ID}"),
            ("POST", f"{URL}{SOME_ID}/test"),
        ],
    )
    def test_read_only_token_cannot_manage(self, client, test_db, admin, method, path):
        _, token = admin
        token.scopes = ["audit_log:read"]
        test_db.flush()
        assert _call(client, token, method, path, json={}).status_code == status.HTTP_403_FORBIDDEN

    def test_unlicensed_org_gets_404(self, client, admin):
        _, token = admin
        with _ee(audit_log_licensed=False):
            resp = client.get(URL, headers=_auth(token))
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestTenantIsolation:
    def test_other_orgs_destinations_are_invisible(self, client, test_db, admin):
        org_id, token = admin
        other_org, _, _ = _member(test_db, "Admin")
        foreign = _destination(test_db, other_org.id)
        scope_to_org(test_db, org_id)

        assert _call(client, token, "GET").json() == []
        assert _call(client, token, "GET", f"{URL}{foreign.id}").status_code == 404
        assert _call(client, token, "DELETE", f"{URL}{foreign.id}").status_code == 404

    def test_rls_hides_them_even_without_the_orm_filter(self, test_db, admin):
        org_id, _ = admin
        other_org, _, _ = _member(test_db, "Admin")
        foreign_id = _destination(test_db, other_org.id).id
        test_db.expunge_all()
        scope_to_org(test_db, org_id)

        with bypass_tenant_filter():
            assert crud.get_destination(test_db, foreign_id) is None
            assert foreign_id not in crud.due_destination_ids(test_db)
