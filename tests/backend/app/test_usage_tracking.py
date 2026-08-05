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


class TestIsHostedModel:
    """Which explicitly-selected Model rows accrue MODEL_TOKENS.

    Only ``rhesis``/``polyphemus`` represent "use Rhesis's own hosted
    infrastructure" as a selectable option in the Models UI. Any other
    provider an org picks for a Model row -- their own ``vertex_ai``,
    ``openai``, self-hosted ``ollama``/``vllm``, whatever -- is their own
    infrastructure choice and must never accrue, regardless of whether
    they happened to leave the key blank.

    (A broader, per-provider classification was tried and reverted: it
    conflated this function's job -- classifying an org's explicit
    choice -- with the system *default*'s job of running on whatever
    the deployment names as ``DEFAULT_*_MODEL``, which
    ``resolve_default_hosted_model`` already handles unconditionally,
    with no provider check at all.)
    """

    @pytest.mark.parametrize("provider", ["rhesis", "polyphemus"])
    def test_rhesis_hosted_providers_accrue_without_an_org_key(self, provider):
        from rhesis.backend.app.utils.user_model_utils import _is_hosted_model

        assert _is_hosted_model(provider, None) is True
        assert _is_hosted_model(provider, "") is True

    @pytest.mark.parametrize("provider", ["rhesis", "polyphemus"])
    def test_rhesis_hosted_providers_do_not_accrue_with_an_org_key(self, provider):
        """An org-supplied key on one of these means a self-hosted or
        custom-endpoint setup using the same protocol, not Rhesis's own
        infrastructure."""
        from rhesis.backend.app.utils.user_model_utils import _is_hosted_model

        assert _is_hosted_model(provider, "sk-org-owned") is False

    @pytest.mark.parametrize(
        "provider",
        ["openai", "gemini", "anthropic", "vertex_ai", "ollama", "vllm", "huggingface"],
    )
    def test_any_org_selected_provider_never_accrues(self, provider):
        """Regardless of whether a key is configured: an explicitly-selected
        Model row for any provider other than rhesis/polyphemus is always
        the org's own infrastructure choice."""
        from rhesis.backend.app.utils.user_model_utils import _is_hosted_model

        assert _is_hosted_model(provider, None) is False
        assert _is_hosted_model(provider, "") is False
        assert _is_hosted_model(provider, "sk-org-owned") is False


class TestResolveDefaultHostedModel:
    """The system default always runs on the server's own credentials."""

    def test_wires_accrual_for_a_non_rhesis_default(self, monkeypatch):
        """Regression: a ``vertex_ai/...`` default used to be handed back as
        a bare string with no callback, so its tokens were never counted."""
        captured = {}

        def fake_get_model(name, **kwargs):
            captured["name"] = name
            captured["on_usage"] = kwargs.get("on_usage")
            return object()

        monkeypatch.setattr("rhesis.backend.app.utils.user_model_utils.get_model", fake_get_model)

        from rhesis.backend.app.utils.user_model_utils import resolve_default_hosted_model

        resolve_default_hosted_model("vertex_ai/gemini-2.5-flash", "org-1")

        assert captured["name"] == "vertex_ai/gemini-2.5-flash"
        assert callable(captured["on_usage"])

    @pytest.mark.parametrize(
        "error", [ValueError("no credentials"), ImportError("torch not installed")]
    )
    def test_falls_back_to_the_bare_string_when_construction_fails(self, error, monkeypatch):
        """Broad on purpose: dropping the provider restriction means this now
        calls get_model for *any* DEFAULT_*_MODEL, including providers whose
        modules raise other error types at import/construction time (e.g.
        huggingface.py raises ImportError without torch/transformers)."""

        def boom(*args, **kwargs):
            raise error

        monkeypatch.setattr("rhesis.backend.app.utils.user_model_utils.get_model", boom)

        from rhesis.backend.app.utils.user_model_utils import resolve_default_hosted_model

        result = resolve_default_hosted_model("vertex_ai/gemini-2.5-flash", "org-1")

        assert result == "vertex_ai/gemini-2.5-flash"

    def test_accrues_against_the_given_org(self, monkeypatch, fake_delay):
        captured = {}
        monkeypatch.setattr(
            "rhesis.backend.app.utils.user_model_utils.get_model",
            lambda name, **kwargs: captured.setdefault("on_usage", kwargs.get("on_usage")),
        )

        from rhesis.backend.app.utils.user_model_utils import resolve_default_hosted_model

        resolve_default_hosted_model("vertex_ai/gemini-2.5-flash", "org-42")
        captured["on_usage"](_usage(30))

        assert fake_delay == [("org-42", QuotaResource.MODEL_TOKENS.value, 30)]

    @pytest.mark.parametrize("organization_id", ["", None])
    def test_no_org_still_builds_the_model_but_wires_no_accrual(self, organization_id, monkeypatch):
        """The test-execution paths derive organization_id from a nullable
        column and can pass "". Booking those tokens against no org at all is
        worse than not counting them, so the model is still built (execution
        must not break) with no callback attached."""
        captured = {}

        def fake_get_model(name, **kwargs):
            captured["kwargs"] = kwargs
            return object()

        monkeypatch.setattr("rhesis.backend.app.utils.user_model_utils.get_model", fake_get_model)

        from rhesis.backend.app.utils.user_model_utils import resolve_default_hosted_model

        result = resolve_default_hosted_model("vertex_ai/gemini-2.5-flash", organization_id)

        assert result is not None
        assert "on_usage" not in captured["kwargs"]
