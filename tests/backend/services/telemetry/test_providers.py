"""Tests for provider resolution.

Which provider served an LLM call, answered from the span when it said so and from the
model name when it did not. Both halves matter: the filter on the traces list groups by
this, so a provider that resolves two different ways shows up twice.
"""

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
