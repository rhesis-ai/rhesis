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


def priced(model: str, input_tokens: int, output_tokens: int):
    """The breakdown Rhesis records for one span, through the code that prices traces.

    Deliberately not ``litellm.cost_per_token`` directly. Asking LiteLLM what it would
    charge and then checking its answer proves nothing about our call into it: a span
    whose prompt and completion counts were passed the wrong way round would price at
    the wrong rates and no assertion built on LiteLLM's own reply would notice. It also
    keeps the failure message when a model stops being priceable, rather than an
    exception from inside LiteLLM.
    """
    costs = calculate_token_costs([llm_span(model, input_tokens, output_tokens)])
    assert costs is not None, f"{model} produced no cost breakdown"
    entry = costs.breakdown[0]
    assert entry.input_cost_usd is not None and entry.output_cost_usd is not None, (
        f"{model} is no longer priceable"
    )
    return entry


def rate_per_million(model: str, *, prompt: int = 0, completion: int = 0) -> float:
    """The per-million rate Rhesis charges for one half of a call."""
    entry = priced(model, prompt, completion)
    tokens = prompt or completion
    return (entry.input_cost_usd + entry.output_cost_usd) / tokens * 1_000_000


def total_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """What Rhesis records for the whole span, with a clear failure if it cannot."""
    costs = calculate_token_costs([llm_span(model, input_tokens, output_tokens)])
    assert costs is not None and costs.total_cost_usd is not None, f"{model} is no longer priceable"
    return costs.total_cost_usd


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
        assert total_cost(model, 1000, 500) > 0

    def test_the_rate_is_in_the_right_units(self, model, provider):
        """A per-token rate read as per-million, or the reverse, is off by 1e6."""
        input_rate = rate_per_million(model, prompt=TOKENS)

        assert MIN_RATE_PER_MILLION < input_rate < MAX_RATE_PER_MILLION

    def test_output_costs_more_than_input(self, model, provider):
        """True of every commercial chat model, and cheap to check.

        Read off one span carrying the same number of tokens each way, so the two
        halves are compared as Rhesis recorded them. That is what catches the counts
        being passed to LiteLLM the wrong way round, which no total would reveal
        because a total adds the same two numbers either way.
        """
        entry = priced(model, TOKENS, TOKENS)

        assert entry.output_cost_usd > entry.input_cost_usd

    def test_each_half_is_charged_to_its_own_side(self, model, provider):
        """A span with only input tokens must cost only input, and the reverse.

        This is what catches the prompt and completion counts being passed to LiteLLM
        the wrong way round. Comparing the two rates does not: with the same number of
        tokens each way the swap changes nothing, and with different numbers output
        still costs more than input either way. A total hides it too, since it adds the
        same two figures whichever side they came from. Sending them to the wrong side
        is only visible when one side is empty.
        """
        input_only = priced(model, TOKENS, 0)
        output_only = priced(model, 0, TOKENS)

        assert input_only.input_cost_usd > 0
        assert input_only.output_cost_usd == 0
        assert output_only.output_cost_usd > 0
        assert output_only.input_cost_usd == 0

    def test_cost_is_linear_in_tokens(self, model, provider):
        """Twice the tokens, twice the cost, at a size below any long-context tier.

        Compared with an absolute tolerance because costs are rounded to six decimal
        places per span and again per trace, so doubling a rounded figure need not equal
        the rounding of the doubled one. A rate whose thousand-token cost does not land
        on a six-place boundary differs by 1e-6, and 112 models in today's price list
        are like that: amazon.nova-2-pro-preview at 2.187e-06 gives 0.002187 against
        0.004375. A relative tolerance would fail those for a rounding artefact rather
        than for a pricing change, which is the opposite of what this file is for.

        The bound is the arithmetic: 5e-7 rounding on the single figure, 1e-6 once
        doubled, 5e-7 on the doubled one, so 1.5e-6 at worst. 2e-6 leaves a little
        room. It is still far tighter than any real non-linearity, which would be a
        tier change and roughly double the figure.
        """
        one = total_cost(model, TOKENS, TOKENS)
        two = total_cost(model, 2 * TOKENS, 2 * TOKENS)

        assert two == pytest.approx(2 * one, rel=1e-6, abs=2e-6)

    def test_it_is_attributed_to_the_provider_the_product_names(self, model, provider):
        """Ties the alias table to what LiteLLM actually returns today.

        command-r comes back as cohere_chat and gemini models as vertex_ai or gemini
        depending on the prefix. If LiteLLM renames one of those, the filter silently
        grows a second row for a provider that already had one.
        """
        assert resolve_provider({}, model) == provider
