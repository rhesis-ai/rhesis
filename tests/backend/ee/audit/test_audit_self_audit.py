"""Reading the audit log records ``audit_log.viewed``, once a minute per actor and credential.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/audit/test_audit_self_audit.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi import status
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text

from rhesis.backend.app.services import cache as cache_module
from rhesis.backend.app.services.audit_events import RepeatWindow
from rhesis.backend.ee.audit import self_audit
from rhesis.backend.events.audit_actions import audit_action
from tests.backend.ee.audit.test_audit_events_api import (
    T0,
    URL,
    _audit_log_registered,  # noqa: F401  (autouse fixture)
    _auth,
    _ee,
    _insert,
    _member,
)
from tests.backend.ee.rbac._rbac_helpers import _assign_org_role
from tests.backend.fixtures.rls import as_org
from tests.backend.fixtures.test_setup import create_test_api_token, create_test_user

pytestmark = [pytest.mark.ee, pytest.mark.integration]


def _read(client, token, path: str = URL, **headers):
    with _ee():
        resp = client.get(path, headers={**_auth(token), **headers})
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return resp


def _viewed(db, org_id) -> list:
    with as_org(db, org_id):
        return list(
            db.execute(
                text(
                    "SELECT actor_type, actor_id, actor_credential_id, actor_credential_hint, "
                    "actor_label, channel, resource_id FROM audit_event "
                    "WHERE organization_id = CAST(:org AS uuid) AND action = :action "
                    "ORDER BY recorded_at, id"
                ),
                {"org": str(org_id), "action": self_audit.VIEWED},
            ).mappings()
        )


class _ClockedRedis:
    """``SET NX EX`` with a clock the test moves."""

    def __init__(self):
        self.now = 0.0
        self._expires: dict[str, float] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and self._expires.get(key, -1) > self.now:
            return None
        self._expires[key] = self.now + ex
        return True

    def delete(self, *keys):
        for key in keys:
            self._expires.pop(key, None)


@contextmanager
def _redis(client):
    """Swap the window's Redis client; ``None`` is Redis unreachable."""
    with (
        patch.object(self_audit._window, "initialize"),
        patch.object(self_audit._window, "_redis", client),
    ):
        yield


@pytest.fixture
def admin(test_db):
    org, user, token = _member(test_db, "Admin")
    return org.id, user.id, token


def test_action_comes_from_the_catalog():
    assert self_audit.VIEWED == audit_action("audit_log:read") == "audit_log.viewed"


class TestOncePerMinute:
    def test_a_list_records_one_row_with_actor_credential_and_channel(self, client, test_db, admin):
        org_id, user_id, token = admin
        _read(client, token, **{"X-Rhesis-Client": "sdk"})

        (row,) = _viewed(test_db, org_id)
        assert row["actor_type"] == "api_token"
        assert row["actor_id"] == user_id
        assert row["actor_credential_id"] == str(token.id)
        assert row["actor_credential_hint"]
        assert row["actor_label"]
        assert row["channel"] == "sdk"
        assert row["resource_id"] is None

    def test_a_second_read_within_the_minute_records_nothing(self, client, test_db, admin):
        org_id, _, token = admin
        _read(client, token)
        _read(client, token)

        assert len(_viewed(test_db, org_id)) == 1

    def test_reading_one_event_records_a_view(self, client, test_db, admin):
        org_id, _, token = admin
        event_id = _insert(test_db, org_id, "endpoint.created", T0)
        _read(client, token, f"{URL}{event_id}")

        assert len(_viewed(test_db, org_id)) == 1

    def test_actions_list_records_nothing(self, client, test_db, admin):
        org_id, _, token = admin
        _read(client, token, f"{URL}actions")

        assert _viewed(test_db, org_id) == []

    def test_a_different_actor_records_its_own(self, client, test_db, admin):
        org_id, user_id, token = admin
        other = create_test_user(
            test_db, org_id, f"audit_other_{uuid.uuid4().hex[:8]}@rhesis-test.com", "Other"
        )
        _assign_org_role(test_db, org_id, other.id, "Admin")
        other_token = create_test_api_token(test_db, other)
        test_db.flush()

        _read(client, token)
        _read(client, other_token)

        assert {r["actor_id"] for r in _viewed(test_db, org_id)} == {user_id, other.id}

    def test_another_credential_of_the_same_actor_records_its_own(self, client, test_db, admin):
        org_id, _, token = admin
        user = token.user
        second = create_test_api_token(test_db, user, name="Second")
        test_db.flush()

        _read(client, token)
        _read(client, second)

        rows = _viewed(test_db, org_id)
        assert {r["actor_credential_id"] for r in rows} == {str(token.id), str(second.id)}

    def test_records_again_after_the_window(self, client, test_db, admin):
        org_id, _, token = admin
        clocked = _ClockedRedis()
        with _redis(clocked):
            _read(client, token)
            clocked.now = self_audit.WINDOW_SECONDS - 1
            _read(client, token)
            assert len(_viewed(test_db, org_id)) == 1

            clocked.now = self_audit.WINDOW_SECONDS
            _read(client, token)
        assert len(_viewed(test_db, org_id)) == 2


class TestRedisUnavailable:
    class _Down:
        def set(self, *args, **kwargs):
            raise RedisConnectionError("down")

    @pytest.mark.parametrize("redis_client", [None, _Down()], ids=["not-connected", "failing"])
    def test_every_read_records(self, client, test_db, admin, redis_client):
        org_id, _, token = admin
        with _redis(redis_client):
            _read(client, token)
            _read(client, token)

        assert len(_viewed(test_db, org_id)) == 2


class _Reachable(_ClockedRedis):
    def __init__(self, failures: int = 0):
        super().__init__()
        self.failures = failures

    def ping(self):
        return True

    def set(self, *args, **kwargs):
        if self.failures:
            self.failures -= 1
            raise RedisConnectionError("dropped")
        return super().set(*args, **kwargs)


class TestReconnect:
    """A fresh window, its connects and clock under the test's control."""

    @pytest.fixture
    def clock(self):
        now = [1000.0]
        with patch("rhesis.backend.app.services.cache.time.monotonic", side_effect=lambda: now[0]):
            yield now

    def test_dedupe_resumes_once_redis_comes_back(self, clock):
        window = RepeatWindow("audit-viewed")
        redis = _Reachable()
        with patch(
            "rhesis.backend.app.services.cache._create_redis_client",
            side_effect=[RedisConnectionError("down"), redis],
        ) as connect:
            assert window.claim("k") is True
            clock[0] += cache_module._RECONNECT_INTERVAL_SECONDS - 1
            assert window.claim("k") is True
            assert connect.call_count == 1

            clock[0] += 1
            assert window.claim("k") is True
            assert window.claim("k") is False
        assert connect.call_count == 2

    def test_a_failed_command_records_and_the_next_one_dedupes(self, clock):
        window = RepeatWindow("audit-viewed")
        redis = _Reachable(failures=1)
        with patch(
            "rhesis.backend.app.services.cache._create_redis_client", return_value=redis
        ) as connect:
            assert window.claim("k") is True
            assert window.claim("k") is True
            assert window.claim("k") is False
        # redis-py reconnects the pool itself; the client is kept.
        connect.assert_called_once()


class TestFailures:
    def test_a_failed_write_fails_the_read_and_frees_the_window(self, client, test_db, admin):
        org_id, _, token = admin
        with (
            patch(
                "rhesis.backend.ee.audit.sink.insert_audit_event",
                side_effect=RuntimeError("write failed"),
            ),
            pytest.raises(RuntimeError),
            _ee(),
        ):
            client.get(URL, headers=_auth(token))

        _read(client, token)
        assert len(_viewed(test_db, org_id)) == 1

    def test_unlicensed_org_records_nothing(self, client, test_db, admin):
        org_id, _, token = admin
        with _ee(audit_log_licensed=False):
            resp = client.get(URL, headers=_auth(token))

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert _viewed(test_db, org_id) == []
