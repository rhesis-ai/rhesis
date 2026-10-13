"""Audit log settings (``/audit-events/settings``) and the privacy options they drive.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/audit/test_audit_settings.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi import status
from sqlalchemy import text

from rhesis.backend.app import models
from rhesis.backend.app.crud.organization import merge_organization_settings
from rhesis.backend.app.provenance import ActorType, Channel, RequestProvenance
from rhesis.backend.app.quota import QuotaPolicy, QuotaRegistry
from rhesis.backend.app.services.beat_heartbeat import beat_signal
from rhesis.backend.app.utils.encryption import decrypt
from rhesis.backend.ee.audit.sink import masked_ip
from tests.backend.ee.audit.test_audit_events_api import (
    URL,
    _audit_log_registered,  # noqa: F401  (autouse fixture)
    _auth,
    _ee,
    _member,
    _no_self_audit,  # noqa: F401  (autouse fixture)
)
from tests.backend.fixtures.rls import as_org

pytestmark = [pytest.mark.ee, pytest.mark.integration]

SETTINGS = f"{URL}settings"


def _get(client, token, path: str = SETTINGS, **params):
    with _ee():
        return client.get(path, params=params, headers=_auth(token))


def _patch(client, token, body: dict):
    with _ee():
        return client.patch(SETTINGS, json=body, headers=_auth(token))


@contextmanager
def _plan_retention(days):
    policy = QuotaPolicy(retention_days=days)
    with patch.object(QuotaRegistry, "get_policy", return_value=policy):
        yield


@pytest.fixture(autouse=True)
def _unlimited_plan():
    # The test licence's plan caps retention; most tests here are about other limits.
    with _plan_retention(None):
        yield


@pytest.fixture(autouse=True)
def _beat_running():
    # Another test's heartbeat may have left the real key; the signal has its own tests.
    with patch.object(beat_signal, "running", return_value=True):
        yield


@pytest.fixture
def admin(test_db):
    org, _, token = _member(test_db, "Admin")
    return org, token


class TestSettings:
    def test_defaults(self, client, admin):
        _, token = admin
        resp = _get(client, token)
        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert resp.json() == {
            "retention_days": 365,
            "max_retention_days": 3650,
            "below_eu_ai_act_minimum": False,
            "mask_ip": True,
            "include_content": False,
            "scheduled_jobs_running": True,
        }

    def test_update_changes_only_what_is_sent(self, client, admin):
        _, token = admin
        resp = _patch(client, token, {"retention_days": 1095, "include_content": True})
        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert _get(client, token).json() == {
            "retention_days": 1095,
            "max_retention_days": 3650,
            "below_eu_ai_act_minimum": False,
            "mask_ip": True,
            "include_content": True,
            "scheduled_jobs_running": True,
        }
        _patch(client, token, {"mask_ip": False, "include_content": None})
        body = _get(client, token).json()
        assert (body["retention_days"], body["mask_ip"], body["include_content"]) == (
            1095,
            False,
            True,
        )

    def test_change_is_recorded_in_the_log(self, client, test_db, admin):
        org, token = admin
        assert _patch(client, token, {"mask_ip": False}).status_code == status.HTTP_200_OK
        with as_org(test_db, org.id):
            rows = test_db.execute(
                text(
                    "SELECT changes FROM audit_event WHERE organization_id = CAST(:org AS uuid) "
                    "AND action = 'organization.updated'"
                ),
                {"org": str(org.id)},
            ).scalars()
            (changes,) = list(rows)
        (change,) = changes
        assert change["field"] == "organization_settings"
        assert change["after"]["audit_log"] == {"mask_ip": False}

    @pytest.mark.parametrize("days", [89, 3651])
    def test_retention_outside_90_days_to_10_years_is_rejected(self, client, admin, days):
        _, token = admin
        resp = _patch(client, token, {"retention_days": days})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.parametrize("days", [90, 3650])
    def test_retention_bounds_are_accepted(self, client, admin, days):
        _, token = admin
        resp = _patch(client, token, {"retention_days": days})
        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert resp.json()["retention_days"] == days

    def test_under_six_months_is_a_warning_not_a_floor(self, client, admin):
        _, token = admin
        resp = _patch(client, token, {"retention_days": 90})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["below_eu_ai_act_minimum"] is True

    def test_unknown_field_is_rejected(self, client, admin):
        _, token = admin
        resp = _patch(client, token, {"retention_days_at_deletion": 9999})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestPlanCap:
    def test_above_the_plan_is_rejected(self, client, admin):
        _, token = admin
        with _plan_retention(365):
            resp = _patch(client, token, {"retention_days": 1095})
            assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert "365" in resp.json()["detail"]
            assert _get(client, token).json()["max_retention_days"] == 365

    def test_a_lower_plan_caps_a_longer_choice(self, client, admin):
        _, token = admin
        _patch(client, token, {"retention_days": 1095})
        with _plan_retention(365):
            assert _get(client, token).json()["retention_days"] == 365

    def test_an_unlimited_plan_stops_at_10_years(self, client, admin):
        _, token = admin
        assert _get(client, token).json()["max_retention_days"] == 3650


class TestScheduledJobs:
    @pytest.mark.parametrize("running", [True, False, None])
    def test_reports_whether_beat_is_running(self, client, admin, running):
        """None is "unknown": Redis could not say. The read still succeeds."""
        _, token = admin
        with patch.object(beat_signal, "running", return_value=running):
            resp = _get(client, token)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["scheduled_jobs_running"] is running


class TestAccess:
    @pytest.mark.parametrize(
        "method, needs", [("get", "audit_log:read"), ("patch", "audit_log:manage")]
    )
    def test_viewer_is_denied(self, client, test_db, method, needs):
        _, _, token = _member(test_db, "Viewer")
        resp = _get(client, token) if method == "get" else _patch(client, token, {})
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.headers.get("X-Accepted-Permissions") == needs

    def test_read_without_manage_can_read_but_not_change(self, client, test_db, admin):
        # Reading the settings needs only audit_log:read, so an Auditor sees them.
        _, token = admin
        token.scopes = ["audit_log:read"]
        test_db.flush()
        assert _get(client, token).status_code == status.HTTP_200_OK
        assert _patch(client, token, {}).status_code == status.HTTP_403_FORBIDDEN

    def test_unlicensed_org_gets_404(self, client, admin):
        _, token = admin
        with _ee(audit_log_licensed=False):
            resp = client.get(SETTINGS, headers=_auth(token))
        assert resp.status_code == status.HTTP_404_NOT_FOUND


def _create_prompt(db, org, user_id, content: str) -> None:
    """Create a prompt as a person, so change capture records it."""
    db.info["_provenance"] = RequestProvenance(
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        credential_id=None,
        credential_hint=None,
        channel=Channel.WEB,
        ip="203.0.113.7",
        user_agent="pytest",
        request_id=f"req-{uuid.uuid4().hex}",
    )
    try:
        db.add(models.Prompt(content=content, organization_id=org.id, user_id=user_id))
        db.flush()
    finally:
        # Request sessions copy test_db.info; they must resolve their own provenance.
        del db.info["_provenance"]


def _prompt_row(db, org_id):
    with as_org(db, org_id):
        return (
            db.execute(
                text(
                    "SELECT id, changes, content_changes FROM audit_event "
                    "WHERE organization_id = CAST(:org AS uuid) AND action = 'prompt.created'"
                ),
                {"org": str(org_id)},
            )
            .mappings()
            .one()
        )


class TestIncludeContent:
    def test_off_drops_the_values(self, client, test_db):
        org, user, token = _member(test_db, "Admin")
        _create_prompt(test_db, org, user.id, "secret prompt")

        row = _prompt_row(test_db, org.id)
        assert row["content_changes"] is None
        assert {"field": "content", "kind": "content"} in row["changes"]
        detail = _get(client, token, f"{URL}{row['id']}").json()
        assert detail["content_changes"] is None

    def test_on_stores_values_encrypted_and_returns_them(self, client, test_db):
        org, user, token = _member(test_db, "Admin")
        merge_organization_settings(test_db, org, {"audit_log": {"include_content": True}})
        test_db.flush()
        _create_prompt(test_db, org, user.id, "secret prompt")

        row = _prompt_row(test_db, org.id)
        assert "secret prompt" not in row["content_changes"]
        assert "secret prompt" in decrypt(row["content_changes"])
        assert "secret prompt" not in str(row["changes"])

        detail = _get(client, token, f"{URL}{row['id']}").json()
        assert {"field": "content", "before": None, "after": "secret prompt"} in (
            detail["content_changes"]
        )
        assert all("content_changes" not in e for e in _get(client, token, URL).json())

        # Turned off later: what was stored is no longer returned.
        _patch(client, token, {"include_content": False})
        assert _get(client, token, f"{URL}{row['id']}").json()["content_changes"] is None


def _prompt_ips(db, org_id) -> list[str]:
    with as_org(db, org_id):
        rows = db.execute(
            text(
                "SELECT ip FROM audit_event WHERE organization_id = CAST(:org AS uuid) "
                "AND action = 'prompt.created' ORDER BY recorded_at, id"
            ),
            {"org": str(org_id)},
        ).scalars()
        return [str(ip) for ip in rows]


class TestMaskIp:
    @pytest.mark.parametrize(
        "ip, masked",
        [("203.0.113.7", "203.0.113.0"), ("2001:db8:abcd:12:1:2:3:4", "2001:db8:abcd::")],
    )
    def test_ipv4_keeps_its_24_and_ipv6_its_48(self, ip, masked):
        assert masked_ip(ip) == masked

    def test_on_by_default_stores_only_the_network(self, client, test_db):
        org, user, token = _member(test_db, "Admin")
        _create_prompt(test_db, org, user.id, "p")

        assert _prompt_ips(test_db, org.id) == ["203.0.113.0"]
        assert [e["ip"] for e in _get(client, token, URL).json()] == ["203.0.113.0"]

    def test_off_stores_the_full_address(self, test_db):
        org, user, _ = _member(test_db, "Admin")
        merge_organization_settings(test_db, org, {"audit_log": {"mask_ip": False}})
        test_db.flush()
        _create_prompt(test_db, org, user.id, "p")

        assert _prompt_ips(test_db, org.id) == ["203.0.113.7"]

    def test_turning_it_off_leaves_earlier_rows_masked(self, test_db):
        org, user, _ = _member(test_db, "Admin")
        _create_prompt(test_db, org, user.id, "before")
        merge_organization_settings(test_db, org, {"audit_log": {"mask_ip": False}})
        test_db.flush()
        _create_prompt(test_db, org, user.id, "after")

        assert _prompt_ips(test_db, org.id) == ["203.0.113.0", "203.0.113.7"]
