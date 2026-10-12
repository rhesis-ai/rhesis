"""Tests for provider resolution.

Which provider served an LLM call, answered from the span when it said so and from the
model name when it did not. Both halves matter: the filter on the traces list groups by
this, so a provider that resolves two different ways shows up twice.
"""

from collections import OrderedDict
from unittest.mock import patch

import pytest
from rhesis.telemetry.attributes import AIAttributes

from rhesis.backend.app.schemas.enrichment import UNKNOWN_PROVIDER
from rhesis.backend.app.services.telemetry.providers import (
    normalize_provider,
    provider_for_model,
    resolve_provider,
)


@pytest.mark.unit
class TestNormalizeProvider:
    """LiteLLM names providers by routing, which splits names we report as one."""

    def test_folds_litellm_routing_names(self):
        assert normalize_provider("vertex_ai") == "gemini"
        assert normalize_provider("cohere_chat") == "cohere"
        assert normalize_provider("text-completion-openai") == "openai"

    def test_folds_the_sdk_own_spellings(self):
        """The SDK names a provider after the company, LiteLLM after how it routes.

        Left unfolded, one company showed as two rows in the provider filter: a Gemini
        call traced through LangChain said google, the same call through Google ADK
        said gemini.
        """
        assert normalize_provider("google") == "gemini"
        assert normalize_provider("mistralai") == "mistral"
        assert normalize_provider("aws") == "bedrock"

    def test_leaves_an_unaliased_provider_alone(self):
        assert normalize_provider("anthropic") == "anthropic"
        # meta names who built the model, not who served it, so it has no LiteLLM
        # counterpart to fold onto and stays as it is.
        assert normalize_provider("meta") == "meta"

    def test_is_case_and_whitespace_insensitive(self):
        assert normalize_provider("  OpenAI ") == "openai"

    def test_nothing_in_means_nothing_out(self):
        assert normalize_provider(None) is None
        assert normalize_provider("") is None
        assert normalize_provider("   ") is None


@pytest.mark.unit
class TestProviderForModel:
    """The fallback for a span that reported no provider."""

    def test_places_a_known_model(self):
        assert provider_for_model("gpt-4") == "openai"

    def test_normalizes_what_litellm_returns(self):
        """A bare gemini model is vertex_ai to LiteLLM but gemini to our integrations."""
        assert provider_for_model("gemini-2.0-flash") == "gemini"

    def test_an_unknown_model_cannot_be_placed(self):
        """LiteLLM raises for anything unprefixed it does not recognise."""
        assert provider_for_model("a-model-litellm-has-never-heard-of") is None

    def test_no_model_name(self):
        assert provider_for_model(None) is None
        assert provider_for_model("") is None


@pytest.mark.unit
class TestResolveProvider:
    """The three tiers, in order."""

    def test_the_span_wins_over_the_model_lookup(self):
        """gpt-4 would resolve to openai, but the span said otherwise."""
        attributes = {AIAttributes.MODEL_PROVIDER: "azure"}

        assert resolve_provider(attributes, "gpt-4") == "azure"

    def test_the_stamped_provider_is_normalized_too(self):
        attributes = {AIAttributes.MODEL_PROVIDER: "vertex_ai"}

        assert resolve_provider(attributes, "gemini-2.0-flash") == "gemini"

    def test_falls_back_to_the_model_name(self):
        assert resolve_provider({}, "gpt-4") == "openai"
        assert resolve_provider(None, "gpt-4") == "openai"

    def test_an_unplaceable_call_is_unknown_not_dropped(self):
        """Its tokens are real, so it is recorded rather than discarded."""
        assert resolve_provider({}, "some-self-hosted-deployment") == UNKNOWN_PROVIDER
        assert resolve_provider(None, None) == UNKNOWN_PROVIDER

    def test_a_stamped_unknown_still_blocks_the_lookup(self):
        """Documents why the SDK must send nothing rather than the word unknown.

        The stamped value wins by design: a span that names its provider knows better
        than a guess from the model name. That makes "unknown" the one value a caller
        must never stamp, because it looks like an answer and stops the lookup that
        would have placed the call. LangChain used to stamp exactly that.
        """
        attributes = {AIAttributes.MODEL_PROVIDER: UNKNOWN_PROVIDER}

        assert resolve_provider(attributes, "gpt-4") == UNKNOWN_PROVIDER
        # Nothing stamped, same span: the lookup places it.
        assert resolve_provider({}, "gpt-4") == "openai"

    def test_an_empty_stamped_value_does_not_win(self):
        attributes = {AIAttributes.MODEL_PROVIDER: ""}

        assert resolve_provider(attributes, "gpt-4") == "openai"


def _make_model_cost(entries):
    """Build a controlled model_cost dict from (key, provider) pairs."""
    return OrderedDict({k: {"litellm_provider": p} for k, p in entries})


def _force_fallback(model_cost):
    """Patch get_llm_provider to always fail and model_cost to the given dict.

    Forces provider_for_model through the model_cost fallback path. Clears
    the lru_cache so prior calls with the same model name don't short-circuit.
    """
    provider_for_model.cache_clear()
    return patch.multiple(
        "litellm",
        get_llm_provider=lambda *a, **kw: (_ for _ in ()).throw(Exception("forced")),
        model_cost=model_cost,
    )


@pytest.mark.unit
class TestModelCostFallback:
    """The model_cost search that runs when get_llm_provider cannot place a model.

    Each test patches litellm so get_llm_provider always fails and model_cost
    contains only the entries the test cares about. This isolates the fallback
    logic from litellm's live data.
    """

    def test_suffix_match(self):
        """vertex_ai/gemini-2.0-flash matches the bare name gemini-2.0-flash."""
        cost = _make_model_cost([("vertex_ai/gemini-2.0-flash", "vertex_ai")])
        with _force_fallback(cost):
            assert provider_for_model("gemini-2.0-flash") == "gemini"

    def test_exact_key_match(self):
        """A model_cost key equal to the model name is the simplest match."""
        cost = _make_model_cost([("gpt-4o", "openai")])
        with _force_fallback(cost):
            assert provider_for_model("gpt-4o") == "openai"

    def test_date_suffix_match(self):
        """command-r-08-2024 (bare key) matches the query command-r."""
        cost = _make_model_cost([("command-r-08-2024", "cohere_chat")])
        with _force_fallback(cost):
            assert provider_for_model("command-r") == "cohere"

    def test_date_suffix_skips_prefixed_keys(self):
        """azure/command-r-plus must not match command-r via date-suffix.

        The date-suffix search only considers bare keys (no /) to avoid
        false positives from provider-prefixed variants of other models.
        """
        cost = _make_model_cost([("azure/command-r-plus", "azure")])
        with _force_fallback(cost):
            assert provider_for_model("command-r") is None

    def test_gateway_providers_are_skipped(self):
        """vercel_ai_gateway accepts any model and tells us nothing."""
        cost = _make_model_cost([
            ("vercel_ai_gateway/cohere/command-r", "vercel_ai_gateway"),
            ("cohere_chat/command-r", "cohere_chat"),
        ])
        with _force_fallback(cost):
            assert provider_for_model("command-r") == "cohere"

    def test_gateway_only_means_no_match(self):
        """When the only match is a gateway, the model cannot be placed."""
        cost = _make_model_cost([("vercel_ai_gateway/cohere/command-r", "vercel_ai_gateway")])
        with _force_fallback(cost):
            assert provider_for_model("command-r") is None

    def test_suffix_match_beats_date_suffix(self):
        """An exact suffix hit in the first pass wins over a date-suffix in the second."""
        cost = _make_model_cost([
            ("some-model-v2", "provider_a"),
            ("openai/some-model", "openai"),
        ])
        with _force_fallback(cost):
            assert provider_for_model("some-model") == "openai"

    def test_no_match_returns_none(self):
        cost = _make_model_cost([("completely-different", "openai")])
        with _force_fallback(cost):
            assert provider_for_model("my-custom-model") is None

    def test_missing_litellm_provider_field_is_skipped(self):
        """A model_cost entry without a litellm_provider field is not a match."""
        provider_for_model.cache_clear()
        bad_cost = OrderedDict({"vertex_ai/gemini-2.0-flash": {"max_tokens": 8192}})
        with patch.multiple(
            "litellm",
            get_llm_provider=lambda *a, **kw: (_ for _ in ()).throw(Exception("forced")),
            model_cost=bad_cost,
        ):
            assert provider_for_model("gemini-2.0-flash") is None
