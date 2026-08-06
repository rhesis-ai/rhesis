"""Unit tests for :mod:`rhesis.backend.app.utils.usage_tracking`.

Pure unit tests -- no database, no Docker, no Celery broker. The task's
`.delay()` is monkeypatched so these verify dispatch behavior in isolation
from the real Celery app and the usage-accounting service.

The sink is only ever handed an already-normalized ``TokenUsage`` by
``BaseLLM._emit_usage``, which also drops empty/zero payloads before they
get here. Provider-dialect parsing is therefore tested at that boundary
(``tests/sdk/models/test_base_usage.py``), not in this file.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.usage_attribution import usage_attribution
from rhesis.backend.app.utils.usage_tracking import (
    UNATTRIBUTED_MARKER,
    UNSTAMPED_MARKER,
    _warned_unstamped,
    accrue_model_tokens,
    install_usage_sink,
    stamp_usage_provenance,
    uninstall_usage_sink,
)
from rhesis.sdk.models.base import BaseLLM


class _StubLLM(BaseLLM):
    """Minimal concrete BaseLLM; no network, no provider SDK."""

    PROVIDER = "stub"

    def load_model(self, *args, **kwargs):
        return None

    def generate_batch(self, *args, **kwargs):
        return []

    def emit(self, total: int) -> None:
        self._emit_usage({"total_tokens": total, "input_tokens": 1, "output_tokens": total - 1})


@pytest.fixture(autouse=True)
def clean_sink():
    """The sink is process-wide state; never let it leak between tests."""
    uninstall_usage_sink()
    yield
    uninstall_usage_sink()


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


def _model(metered):
    return stamp_usage_provenance(_StubLLM("stub/model"), metered)


class TestAccrueModelTokens:
    def test_accrues_metered_tokens_to_the_ambient_org(self, fake_delay):
        with usage_attribution("org-1"):
            accrue_model_tokens(_usage(123), _model(True))

        assert fake_delay == [("org-1", QuotaResource.MODEL_TOKENS.value, 123)]

    def test_an_orgs_own_api_key_never_accrues(self, fake_delay):
        """The credential-provenance rule: if the org supplied the key, it
        already pays the provider directly and must not also pay us."""
        with usage_attribution("org-1"):
            accrue_model_tokens(_usage(500), _model(False))

        assert fake_delay == []

    def test_bills_the_org_that_is_ambient_now_not_at_construction(self, fake_delay):
        """One model instance reused across two orgs' work bills each
        correctly. The old per-instance closure could not do this -- it
        captured one org id for the life of the model."""
        model = _model(True)

        with usage_attribution("org-a"):
            accrue_model_tokens(_usage(2), model)
        with usage_attribution("org-b"):
            accrue_model_tokens(_usage(3), model)

        assert fake_delay == [
            ("org-a", QuotaResource.MODEL_TOKENS.value, 2),
            ("org-b", QuotaResource.MODEL_TOKENS.value, 3),
        ]

    def test_unstamped_model_still_accrues_and_warns(self, fake_delay, caplog):
        """A model built outside the resolution layer has no provenance. The
        deployment defaults reached that way run on our credentials, so the
        safe reading is to bill and complain -- treating "unknown" as "free"
        is the silent undercount this whole mechanism replaces."""
        with caplog.at_level("WARNING"), usage_attribution("org-1"):
            accrue_model_tokens(_usage(7), _StubLLM("stub/unstamped"))

        assert fake_delay == [("org-1", QuotaResource.MODEL_TOKENS.value, 7)]
        assert UNSTAMPED_MARKER in caplog.text

    def test_unmetered_model_is_never_even_mentioned_in_the_log(self, fake_delay, caplog):
        """An org running on its own API key is none of our accounting's
        business: no accrual, and nothing about their model in our logs."""
        model = _model(False)
        model.api_key = "sk-org-owned"

        with caplog.at_level("DEBUG"), usage_attribution("org-1"):
            accrue_model_tokens(_usage(1_000_000), model)

        assert fake_delay == []
        assert caplog.text == ""

    def test_an_unstamped_model_holding_its_own_key_is_not_billed(self, fake_delay, caplog):
        """The safety net. Connection tests build a model straight from
        credentials the user just typed in and run a real generation on it.
        Nobody stamps those, and billing them would charge the org for tokens
        their own provider already charged them for."""
        model = _StubLLM("openai/gpt-4o")
        model.api_key = "sk-org-owned"

        with caplog.at_level("WARNING"), usage_attribution("org-1"):
            accrue_model_tokens(_usage(500), model)

        assert fake_delay == []

    def test_an_unstamped_model_holding_our_key_is_still_billed(self, fake_delay, monkeypatch):
        """The other direction, and the reason "has a key" is not the test:
        RhesisLLM and PolyphemusLLM both fall back to `os.getenv
        ("RHESIS_API_KEY")`, so an unstamped hosted default holds *our* key.
        Exempting it would silently stop billing the main hosted provider."""
        monkeypatch.setattr(
            "rhesis.backend.app.utils.usage_tracking.get_rhesis_settings",
            lambda: SimpleNamespace(api_key="rh-ours"),
        )
        model = _StubLLM("rhesis/rhesis-default")
        model.api_key = "rh-ours"

        with usage_attribution("org-1"):
            accrue_model_tokens(_usage(70), model)

        assert fake_delay == [("org-1", QuotaResource.MODEL_TOKENS.value, 70)]

    def test_no_log_line_ever_contains_an_api_key(self, fake_delay, caplog):
        """Every branch that logs, with a key present, over both the
        formatted text and the structured fields the JSON formatter forwards."""
        secret = "sk-super-secret-value"

        for metered, org in ((None, "org-1"), (None, None), (True, None)):
            caplog.clear()
            _warned_unstamped.clear()
            model = stamp_usage_provenance(_StubLLM("openai/gpt-4o"), metered)
            model.api_key = secret

            with caplog.at_level("DEBUG"), usage_attribution(org):
                accrue_model_tokens(_usage(11), model)

            assert secret not in caplog.text
            for record in caplog.records:
                assert secret not in str(record.__dict__)

    def test_unstamped_warning_is_not_repeated_per_call(self, fake_delay, caplog):
        model = _StubLLM("stub/hot-loop")
        with caplog.at_level("WARNING"), usage_attribution("org-1"):
            for _ in range(5):
                accrue_model_tokens(_usage(1), model)

        assert caplog.text.count(UNSTAMPED_MARKER) == 1

    def test_no_ambient_org_is_counted_as_unattributed_not_dropped(self, fake_delay, caplog):
        """Real tokens with nowhere to bill them are a defect in the binding,
        not a reason to pretend they did not happen."""
        with caplog.at_level("WARNING"):
            accrue_model_tokens(_usage(42), _model(True))

        assert fake_delay == []
        assert UNATTRIBUTED_MARKER in caplog.text
        record = next(r for r in caplog.records if getattr(r, "usage_marker", None))
        assert record.usage_marker == UNATTRIBUTED_MARKER
        assert record.total_tokens == 42

    def test_unmetered_model_with_no_org_is_not_unattributed(self, caplog):
        """Nothing to bill in the first place, so this is not a miss."""
        with caplog.at_level("WARNING"):
            accrue_model_tokens(_usage(9), _model(False))

        assert UNATTRIBUTED_MARKER not in caplog.text

    def test_dispatch_failure_is_swallowed(self, monkeypatch):
        """A broker outage must never raise back into the LLM call site."""

        def boom(*args, **kwargs):
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr("rhesis.backend.tasks.usage.accrue_usage.delay", boom)

        with usage_attribution("org-1"):
            accrue_model_tokens(_usage(10), _model(True))  # must not raise

    def test_does_not_touch_the_database_synchronously(self, monkeypatch):
        """The whole point of queueing instead of writing inline: no
        SessionLocal() / DB call happens in the calling thread."""
        called = []
        monkeypatch.setattr("rhesis.backend.app.database.SessionLocal", lambda: called.append(True))
        monkeypatch.setattr("rhesis.backend.tasks.usage.accrue_usage.delay", lambda *a, **k: None)

        with usage_attribution("org-1"):
            accrue_model_tokens(_usage(10), _model(True))

        assert called == []


class TestSinkInstallation:
    """The point of the whole design: nobody has to wire anything up."""

    def test_a_model_nobody_wired_still_accrues(self, fake_delay):
        install_usage_sink()

        # No on_usage passed, no accrual code anywhere near the call site.
        model = stamp_usage_provenance(_StubLLM("stub/model"), True)
        with usage_attribution("org-1"):
            model.emit(64)

        assert fake_delay == [("org-1", QuotaResource.MODEL_TOKENS.value, 64)]

    def test_an_instance_listener_does_not_detach_the_sink(self, fake_delay):
        """``routers/services.py`` swaps ``on_usage`` to relay usage back to
        an SDK caller. That must not also opt the model out of billing."""
        install_usage_sink()
        seen = []
        model = stamp_usage_provenance(_StubLLM("stub/model"), True)
        model.on_usage = seen.append

        with usage_attribution("org-1"):
            model.emit(20)

        assert [u["total_tokens"] for u in seen] == [20]
        assert fake_delay == [("org-1", QuotaResource.MODEL_TOKENS.value, 20)]

    def test_no_sink_installed_means_no_accrual(self, fake_delay):
        model = stamp_usage_provenance(_StubLLM("stub/model"), True)
        with usage_attribution("org-1"):
            model.emit(64)

        assert fake_delay == []


class TestStampUsageProvenance:
    def test_tolerates_a_bare_provider_string(self):
        """The resolution chain still degrades to a string on construction
        failure, so callers should not each need an isinstance check."""
        assert stamp_usage_provenance("vertex_ai/gemini-2.5-flash", True) == (
            "vertex_ai/gemini-2.5-flash"
        )


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

    def test_stamps_a_non_rhesis_default_as_metered(self, monkeypatch):
        """Regression: a ``vertex_ai/...`` default used to be handed back as
        a bare string with no accrual, so its tokens were never counted."""
        monkeypatch.setattr(
            "rhesis.backend.app.utils.user_model_utils.get_model",
            lambda name, **kwargs: _StubLLM(name),
        )

        from rhesis.backend.app.utils.user_model_utils import resolve_default_hosted_model

        model = resolve_default_hosted_model("vertex_ai/gemini-2.5-flash")

        assert model.model_name == "vertex_ai/gemini-2.5-flash"
        assert model.usage_metered is True

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

        assert resolve_default_hosted_model("vertex_ai/gemini-2.5-flash") == (
            "vertex_ai/gemini-2.5-flash"
        )

    def test_a_user_with_no_configured_model_gets_the_stamped_default(self, monkeypatch):
        """Covers `_get_user_model`'s no-model_id branch, which nothing
        exercised -- an arity mistake here shipped past the whole suite once.

        Also the case peqy flagged on #2355: this branch used to pass
        `str(user.organization_id)`, which is the string "None" for an
        orgless user, straight into accrual. There is no org argument to get
        wrong now.
        """
        monkeypatch.setattr(
            "rhesis.backend.app.utils.user_model_utils.get_model",
            lambda name, **kwargs: _StubLLM(name),
        )

        from rhesis.backend.app.utils.user_model_utils import _get_user_model

        user = SimpleNamespace(
            organization_id=None,
            settings=SimpleNamespace(
                models=SimpleNamespace(generation=SimpleNamespace(model_id=None))
            ),
        )
        model = _get_user_model(db=None, user=user, purpose="generation", default_model="rhesis/x")

        assert model.model_name == "rhesis/x"
        assert model.usage_metered is True

    def test_accrues_against_whatever_org_is_ambient(self, monkeypatch, fake_delay):
        install_usage_sink()
        monkeypatch.setattr(
            "rhesis.backend.app.utils.user_model_utils.get_model",
            lambda name, **kwargs: _StubLLM(name),
        )

        from rhesis.backend.app.utils.user_model_utils import resolve_default_hosted_model

        model = resolve_default_hosted_model("vertex_ai/gemini-2.5-flash")
        with usage_attribution("org-42"):
            model.emit(30)

        assert fake_delay == [("org-42", QuotaResource.MODEL_TOKENS.value, 30)]
