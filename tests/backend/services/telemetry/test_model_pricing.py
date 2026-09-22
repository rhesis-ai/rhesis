"""Guards against LiteLLM's price list changing underneath us.

Every other pricing test in this suite works out its expected figure by calling
``litellm.cost_per_token`` with the same arguments as the code under test, so it
compares LiteLLM against itself and can never disagree. LiteLLM is pinned only as
``>=1.84.0``, and is deliberately excluded from the repo's exclude-newer date pin, so it
floats to the newest release on every resolve. A release that renames or drops a model
would stop pricing it, ``_price_span`` would swallow the exception, and every test would
still pass.

What can be asserted without copying a price list into the repo is the shape of the
answer: that a model we name is still priceable at all, that the figure is in the right
units, that output costs more than input, and that cost is linear in tokens. Those are
true of every commercial chat model and none of them can be satisfied by a broken
lookup.

Deliberately no exact rates. A provider changing its prices is normal and must not
break the build; LiteLLM losing the ability to price a provider at all is not.
"""

from unittest.mock import Mock

import litellm
import pytest
from rhesis.telemetry.attributes import AIAttributes

from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.services.telemetry.enrichment import calculate_token_costs
from rhesis.backend.app.services.telemetry.providers import resolve_provider

# One model per provider Rhesis claims to support, and the provider name the product
# shows for it after normalisation. A rename or a removal upstream fails here by name,
# which is the point: the failure says which provider stopped being priceable.
CANONICAL_MODELS = [
    ("gpt-4o", "openai"),
    ("claude-sonnet-4-5", "anthropic"),
    ("gemini/gemini-2.5-flash", "gemini"),
    ("mistral/mistral-large-latest", "mistral"),
    ("command-r", "cohere"),
]

# Sanity bounds on the per-million-token rate, not a claim about anybody's pricing. A
# units slip, the realistic failure, is off by a factor of a million and lands far
# outside these.
MIN_RATE_PER_MILLION = 0.001
MAX_RATE_PER_MILLION = 1000.0

# Small enough to stay under any long-context tier. LiteLLM charges claude-sonnet-4-5
# double above 200k prompt tokens, so a million-token probe measures the wrong rate.
TOKENS = 1000


def rate_per_million(model: str, *, prompt: int = 0, completion: int = 0) -> float:
    """The per-million rate LiteLLM would charge for one half of a call."""
    input_cost, output_cost = litellm.cost_per_token(
        model=model, prompt_tokens=prompt, completion_tokens=completion
    )
    tokens = prompt or completion
    return (input_cost + output_cost) / tokens * 1_000_000


def llm_span(model: str, input_tokens: int, output_tokens: int) -> Trace:
    return Mock(
        spec=Trace,
        span_id="span1",
        attributes={
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
            AIAttributes.MODEL_NAME: model,
            AIAttributes.LLM_TOKENS_INPUT: input_tokens,
            AIAttributes.LLM_TOKENS_OUTPUT: output_tokens,
        },
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("model", "provider"),
    CANONICAL_MODELS,
    ids=[model for model, _ in CANONICAL_MODELS],
)
class TestEveryProviderStaysPriceable:
    """One model per provider, checked through the code that actually prices spans."""

    def test_it_still_prices(self, model, provider):
        """The failure this whole file exists for.

        An unpriceable model is recorded with no cost, which reads on screen as "No
        cost data" rather than as an error, so nothing else would report it.
        """
        costs = calculate_token_costs([llm_span(model, 1000, 500)])

        assert costs is not None
        assert costs.total_cost_usd is not None, f"{model} is no longer priceable"
        assert costs.total_cost_usd > 0

    def test_the_rate_is_in_the_right_units(self, model, provider):
        """A per-token rate read as per-million, or the reverse, is off by 1e6."""
        input_rate = rate_per_million(model, prompt=TOKENS)

        assert MIN_RATE_PER_MILLION < input_rate < MAX_RATE_PER_MILLION

    def test_output_costs_more_than_input(self, model, provider):
        """True of every commercial chat model, and cheap to check.

        Catches the two halves being swapped, which no total would reveal.
        """
        input_rate = rate_per_million(model, prompt=TOKENS)
        output_rate = rate_per_million(model, completion=TOKENS)

        assert output_rate > input_rate

    def test_cost_is_linear_in_tokens(self, model, provider):
        """Twice the tokens, twice the cost, at a size below any long-context tier."""
        one = calculate_token_costs([llm_span(model, TOKENS, TOKENS)]).total_cost_usd
        two = calculate_token_costs([llm_span(model, 2 * TOKENS, 2 * TOKENS)]).total_cost_usd

        assert two == pytest.approx(2 * one, rel=1e-6)

    def test_it_is_attributed_to_the_provider_the_product_names(self, model, provider):
        """Ties the alias table to what LiteLLM actually returns today.

        command-r comes back as cohere_chat and gemini models as vertex_ai or gemini
        depending on the prefix. If LiteLLM renames one of those, the filter silently
        grows a second row for a provider that already had one.
        """
        assert resolve_provider({}, model) == provider
