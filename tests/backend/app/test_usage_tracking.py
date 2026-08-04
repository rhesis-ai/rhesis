"""Unit tests for :mod:`rhesis.backend.app.utils.usage_tracking`.

Pure unit tests -- no database, no Docker, no Celery broker. The task's
`.delay()` is monkeypatched so these verify dispatch behavior in isolation
from the real Celery app and the usage-accounting service.

The callback is only ever handed an already-normalized ``TokenUsage`` by
``BaseLLM._emit_usage``, which also drops empty/zero payloads before they
get here. Provider-dialect parsing is therefore tested at that boundary
(``tests/sdk/models/test_base_usage.py``), not in this file.
"""

from __future__ import annotations

import pytest

from rhesis.backend.app.quota import QuotaResource


@pytest.fixture
def fake_delay(monkeypatch):
    """Capture calls to accrue_usage.delay(...) without a broker."""
    recorded = []
    monkeypatch.setattr(
        "rhesis.backend.tasks.usage.accrue_usage.delay",
        lambda *args, **kwargs: recorded.append(args),
    )
    return recorded


def _usage(total: int) -> dict:
    return {"input_tokens": 1, "output_tokens": total - 1, "total_tokens": total}


class TestMakeUsageAccrualCallback:
    def test_dispatches_model_tokens_accrual(self, fake_delay):
        from rhesis.backend.app.utils.usage_tracking import make_usage_accrual_callback

        make_usage_accrual_callback("org-1")(_usage(123))

        assert fake_delay == [("org-1", QuotaResource.MODEL_TOKENS.value, 123)]

    def test_dispatch_failure_is_swallowed(self, monkeypatch):
        """A broker outage (or any dispatch error) must never raise back
        into the LLM call site."""

        def boom(*args, **kwargs):
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr("rhesis.backend.tasks.usage.accrue_usage.delay", boom)

        from rhesis.backend.app.utils.usage_tracking import make_usage_accrual_callback

        # Must not raise.
        make_usage_accrual_callback("org-1")(_usage(10))

    def test_each_callback_uses_its_own_org_id(self, fake_delay):
        """Separate callbacks (e.g. two different orgs' models in the same
        process) never cross-contaminate -- organization_id is closed over
        per callback, not read from shared/global state."""
        from rhesis.backend.app.utils.usage_tracking import make_usage_accrual_callback

        make_usage_accrual_callback("org-a")(_usage(2))
        make_usage_accrual_callback("org-b")(_usage(3))

        assert fake_delay == [
            ("org-a", QuotaResource.MODEL_TOKENS.value, 2),
            ("org-b", QuotaResource.MODEL_TOKENS.value, 3),
        ]

    def test_does_not_touch_the_database_synchronously(self, monkeypatch):
        """The whole point of queueing instead of writing inline: no
        SessionLocal() / DB call happens in the calling thread."""
        called = []
        monkeypatch.setattr(
            "rhesis.backend.app.database.SessionLocal",
            lambda: called.append(True),
        )
        monkeypatch.setattr(
            "rhesis.backend.tasks.usage.accrue_usage.delay",
            lambda *a, **k: None,
        )

        from rhesis.backend.app.utils.usage_tracking import make_usage_accrual_callback

        make_usage_accrual_callback("org-1")(_usage(10))

        assert called == []
