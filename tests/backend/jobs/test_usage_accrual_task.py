"""Unit tests for the `accrue_usage` Celery task.

Pure unit tests -- no database, no Docker, no broker. Calling a
`bind=True` Celery task directly (not via `.delay()`) runs its body
synchronously with `self` bound to the task instance, which is the
standard way to unit test task logic without a broker.
"""

from __future__ import annotations

import pytest

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.jobs.usage import accrue_usage


class _FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def fake_session(monkeypatch):
    session = _FakeSession()
    monkeypatch.setattr("rhesis.backend.jobs.usage.SessionLocal", lambda: session)
    return session


@pytest.fixture
def fake_bind_scope(monkeypatch):
    recorded = []
    monkeypatch.setattr(
        "rhesis.backend.jobs.usage.bind_scope_to_session",
        lambda db, org_id: recorded.append((db, org_id)),
    )
    return recorded


@pytest.fixture
def recorded_increments(monkeypatch):
    recorded = []
    monkeypatch.setattr(
        "rhesis.backend.jobs.usage.increment_usage",
        lambda db, org_id, resource, amount: recorded.append((org_id, resource, amount)),
    )
    return recorded


class TestAccrueUsage:
    def test_binds_scope_and_increments_usage(
        self, fake_session, fake_bind_scope, recorded_increments
    ):
        accrue_usage("org-1", QuotaResource.MODEL_TOKENS.value, 123)

        assert fake_bind_scope == [(fake_session, "org-1")]
        assert recorded_increments == [("org-1", QuotaResource.MODEL_TOKENS, 123)]

    @pytest.mark.parametrize("resource", list(QuotaResource))
    def test_handles_every_quota_resource(
        self, resource, fake_session, fake_bind_scope, recorded_increments
    ):
        """One task serves all resources, so each member must round-trip
        through the broker's string form back to its enum."""
        accrue_usage("org-1", resource.value, 7)

        assert recorded_increments == [("org-1", resource, 7)]

    def test_unknown_resource_raises_without_retrying(self, fake_session, fake_bind_scope):
        """A bad resource name is a programming error, not a transient
        fault -- it must surface immediately rather than burn three
        retries. The conversion happens before the session is even opened.
        """
        with pytest.raises(ValueError):
            accrue_usage("org-1", "not_a_resource", 5)

        assert fake_bind_scope == []

    def test_closes_session_after_use(self, fake_session, fake_bind_scope, recorded_increments):
        accrue_usage("org-1", QuotaResource.SEATS.value, 10)

        assert fake_session.closed is True

    def test_retries_on_increment_usage_failure(self, fake_session, fake_bind_scope, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("db unreachable")

        monkeypatch.setattr("rhesis.backend.jobs.usage.increment_usage", boom)

        with pytest.raises(RuntimeError):
            accrue_usage("org-1", QuotaResource.TRACING_SPANS.value, 10)

    def test_closes_session_even_when_retrying(self, fake_session, fake_bind_scope, monkeypatch):
        monkeypatch.setattr(
            "rhesis.backend.jobs.usage.increment_usage",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db unreachable")),
        )

        with pytest.raises(RuntimeError):
            accrue_usage("org-1", QuotaResource.TRACING_SPANS.value, 10)

        assert fake_session.closed is True
