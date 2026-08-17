"""The MODEL_TOKENS gate in :mod:`rhesis.backend.app.utils.user_model_utils`.

Pure unit tests -- no database, no Docker. ``_enforce_model_token_quota`` is
monkeypatched to always raise, so these check *whether the gate is reached
at all*, not its blocking arithmetic (covered by ``test_quota_enforcement.py``).

The regression this guards is the one that matters most: an org running on
its own provider key must never be blocked by *our* token quota, because
their call was never going to cost us anything. ``_is_hosted_model`` is the
single predicate deciding that for every branch of
``_fetch_and_configure_model`` -- see its docstring.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError, QuotaVerdict


def _always_blocks(db, organization_id):
    """A stand-in for ``_enforce_model_token_quota`` that always raises, so a
    passing construction call proves the gate was never reached -- not that
    it happened to evaluate as allowed. Patched at this level (rather than
    the ``enforce_quota`` it wraps) so these tests need no real ``db``: the
    real helper's own DB lookup is skipped entirely, and only whether it
    gets *called at all* is under test here."""
    raise QuotaExceededError(
        QuotaVerdict(
            resource=QuotaResource.MODEL_TOKENS,
            used=999,
            limit=1,
            allowed=False,
            over_limit=True,
        )
    )


@pytest.fixture
def blocking_gate(monkeypatch):
    """Install `_always_blocks` as `_enforce_model_token_quota` for the test."""
    monkeypatch.setattr(
        "rhesis.backend.app.utils.user_model_utils._enforce_model_token_quota", _always_blocks
    )


@pytest.fixture
def configured_model(monkeypatch):
    """Build a Model row stub and run it through `_fetch_and_configure_model`.

    Mirrors the fixture of the same name in `test_usage_tracking.py`'s
    `TestConfiguredModelProvenance`, duplicated rather than imported: that
    fixture is class-scoped there, and this file's concern (does the gate
    fire) is deliberately separate from provenance stamping.
    """

    def _resolve(*, provider="openai", key=""):
        model_row = SimpleNamespace(
            name="configured",
            model_name="gpt-4o",
            key=key,
            endpoint="http://self-hosted.internal:8000" if not key else None,
            provider_type=SimpleNamespace(type_value=provider),
        )
        monkeypatch.setattr(
            "rhesis.backend.app.utils.user_model_utils.model_crud.get_model",
            lambda **kwargs: model_row,
        )
        monkeypatch.setattr(
            "rhesis.backend.app.utils.user_model_utils.get_model",
            lambda **kwargs: SimpleNamespace(model_name=kwargs.get("model_name", "gpt-4o")),
        )
        from rhesis.backend.app.utils.user_model_utils import _fetch_and_configure_model

        return _fetch_and_configure_model(None, "model-1", "org-1", "vertex_ai/default")

    return _resolve


class TestTokenGateFiresOnlyForHostedModels:
    @pytest.mark.parametrize("provider", ["rhesis", "polyphemus"])
    def test_hosted_provider_with_no_org_key_is_blocked(
        self, configured_model, blocking_gate, provider
    ):
        """`rhesis`/`polyphemus` with no stored key run on our credentials --
        this is exactly what `_is_hosted_model` returns True for."""
        with pytest.raises(QuotaExceededError):
            configured_model(provider=provider, key="")

    @pytest.mark.parametrize("provider", ["rhesis", "polyphemus"])
    def test_hosted_provider_with_an_org_key_is_not_blocked(
        self, configured_model, blocking_gate, provider
    ):
        """An org-supplied key on a hosted-provider row means self-hosted or
        custom-endpoint use of the same protocol, not our infrastructure --
        `_is_hosted_model` is False, so the gate must not even run."""
        model = configured_model(provider=provider, key="sk-org-owned")

        assert model.model_name == "gpt-4o"

    @pytest.mark.parametrize(
        "provider", ["openai", "gemini", "anthropic", "vertex_ai", "ollama", "vllm"]
    )
    def test_a_provider_rhesis_does_not_supply_is_never_blocked(
        self, configured_model, blocking_gate, provider
    ):
        """The regression that matters most: an org's own provider key must
        never be blocked by our token quota, whatever it is -- their call
        was never going to cost us anything."""
        model = configured_model(provider=provider, key="sk-org-owned")

        assert model.model_name == "gpt-4o"

    def test_a_keyless_self_hosted_row_is_never_blocked(self, configured_model, blocking_gate):
        """A keyless self-hosted row (own endpoint, no key) is not a hosted
        model either -- still the org's own infrastructure."""
        model = configured_model(provider="vllm", key="")

        assert model.model_name == "gpt-4o"


class TestResolveDefaultHostedModelTokenGate:
    """The system default is unconditionally ours to pay for (see
    `resolve_default_hosted_model`'s docstring), so the gate always fires
    here regardless of provider -- the inverse of the row-level gate above.
    """

    def test_blocked_when_the_gate_fires(self, blocking_gate, monkeypatch):
        monkeypatch.setattr(
            "rhesis.backend.app.utils.user_model_utils.get_model",
            lambda name, **kwargs: SimpleNamespace(model_name=name),
        )
        from rhesis.backend.app.utils.user_model_utils import resolve_default_hosted_model

        with pytest.raises(QuotaExceededError):
            resolve_default_hosted_model("rhesis/default", db=None, organization_id="org-1")

    def test_no_organization_id_skips_the_check_instead_of_raising(self, monkeypatch, caplog):
        """A last-resort escape hatch, not a silent bypass: an org-less
        construction path logs rather than raising or blocking."""
        monkeypatch.setattr(
            "rhesis.backend.app.utils.user_model_utils.get_model",
            lambda name, **kwargs: SimpleNamespace(model_name=name),
        )
        from rhesis.backend.app.utils.user_model_utils import resolve_default_hosted_model

        with caplog.at_level("WARNING"):
            model = resolve_default_hosted_model("rhesis/default", db=None, organization_id=None)

        assert model.model_name == "rhesis/default"
        assert "No organization_id" in caplog.text
