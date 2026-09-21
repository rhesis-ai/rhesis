"""Tests for trace_usage_totals.

The accessor that reports what a trace spent. Its job is to answer the same way for a
blob written by a current worker and one written before the trace-level input/output
split existed, so the new figures appear on traces already in the database without a
backfill or a re-enrichment pass.
"""

import pytest

from rhesis.backend.app.services.telemetry.token_totals import (
    TraceUsage,
    trace_summary_usage,
    trace_usage_totals,
)


def breakdown_entry(span_id, model, input_tokens, output_tokens, in_cost, out_cost, provider=None):
    """One priced span, shaped the way enrichment writes it."""
    entry = {
        "span_id": span_id,
        "model_name": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost_usd": in_cost,
        "output_cost_usd": out_cost,
        "total_cost_usd": in_cost + out_cost,
        "input_cost_eur": in_cost * 0.9,
        "output_cost_eur": out_cost * 0.9,
        "total_cost_eur": (in_cost + out_cost) * 0.9,
    }
    if provider is not None:
        entry["provider"] = provider
    return entry


def current_blob():
    """What a worker on this version writes: every rolled-up key present."""
    return {
        "costs": {
            "total_cost_usd": 0.03,
            "total_cost_eur": 0.027,
            "total_input_cost_usd": 0.02,
            "total_output_cost_usd": 0.01,
            "total_input_tokens": 300,
            "total_output_tokens": 120,
            "total_tokens": 420,
            "models_used": ["gpt-4"],
            "providers_used": ["openai"],
            "breakdown": [breakdown_entry("a", "gpt-4", 300, 120, 0.02, 0.01, "openai")],
        }
    }


def legacy_blob():
    """What is actually in the database today: a breakdown and nothing rolled up.

    No total_input_cost_usd, no models_used, no providers_used, and no per-span
    provider -- the shape every already-enriched trace carries.
    """
    return {
        "costs": {
            "total_cost_usd": 0.03,
            "total_cost_eur": 0.027,
            "total_input_tokens": 300,
            "total_output_tokens": 120,
            "total_tokens": 420,
            "breakdown": [
                breakdown_entry("a", "gpt-4", 200, 100, 0.015, 0.008),
                breakdown_entry("b", "gemini-2.0-flash", 100, 20, 0.005, 0.002),
            ],
        }
    }


@pytest.mark.unit
class TestCurrentBlob:
    """When the rolled-up keys are there, they are used as-is."""

    def test_reads_every_figure(self):
        usage = trace_usage_totals(current_blob())

        assert usage.input_tokens == 300
        assert usage.output_tokens == 120
        assert usage.total_tokens == 420
        assert usage.input_cost_usd == pytest.approx(0.02)
        assert usage.output_cost_usd == pytest.approx(0.01)
        assert usage.total_cost_usd == pytest.approx(0.03)
        assert usage.total_cost_eur == pytest.approx(0.027)
        assert usage.models == ["gpt-4"]
        assert usage.providers == ["openai"]


@pytest.mark.unit
class TestLegacyBlob:
    """A blob predating the rollup still reports the same numbers."""

    def test_derives_the_cost_split_from_the_breakdown(self):
        usage = trace_usage_totals(legacy_blob())

        assert usage.input_cost_usd == pytest.approx(0.02)
        assert usage.output_cost_usd == pytest.approx(0.01)

    def test_the_derived_split_adds_up_to_the_stored_total(self):
        """Not a tautology: the total is stored, the halves are summed separately."""
        usage = trace_usage_totals(legacy_blob())

        assert usage.input_cost_usd + usage.output_cost_usd == pytest.approx(
            usage.total_cost_usd, abs=1e-6
        )

    def test_derives_models_from_the_breakdown(self):
        """Ordered by model name, not by where they appear in the breakdown.

        The list orders by the alphabetically first model, so this is what keeps the
        cell and the sort naming the same one. See TestModelsPairWithTheirOwnProviders.
        """
        usage = trace_usage_totals(legacy_blob())

        assert usage.models == ["gemini-2.0-flash", "gpt-4"]

    def test_derives_providers_from_the_model_names(self):
        """No entry carries a provider, so each is placed from its own model."""
        usage = trace_usage_totals(legacy_blob())

        assert usage.providers == ["gemini", "openai"]

    def test_an_unplaceable_model_is_unknown_not_missing(self):
        blob = legacy_blob()
        blob["costs"]["breakdown"] = [breakdown_entry("a", "self-hosted-7b", 10, 5, 0.0, 0.0)]

        usage = trace_usage_totals(blob)

        assert usage.models == ["self-hosted-7b"]
        assert usage.providers == ["unknown"]


@pytest.mark.unit
class TestBlobPredatingTheTokenFields:
    """Older still: a breakdown with no trace-level token totals either."""

    def test_derives_the_token_split_from_the_breakdown(self):
        blob = legacy_blob()
        for key in ("total_tokens", "total_input_tokens", "total_output_tokens"):
            blob["costs"].pop(key)

        usage = trace_usage_totals(blob, llm_tokens_fallback=999)

        assert usage.input_tokens == 300
        assert usage.output_tokens == 120
        assert usage.total_tokens == 420

    def test_falls_back_to_sql_when_the_breakdown_is_empty_too(self):
        blob = {"costs": {"total_cost_usd": 0.0, "breakdown": []}}

        usage = trace_usage_totals(blob, llm_tokens_fallback=777)

        assert usage.total_tokens == 777
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0


@pytest.mark.unit
class TestUnenrichedTrace:
    """No blob at all: tokens come from SQL, cost is simply not known yet."""

    def test_uses_the_sql_token_fallback(self):
        usage = trace_usage_totals(None, llm_tokens_fallback=420)

        assert usage == TraceUsage(total_tokens=420)

    def test_an_empty_blob_is_the_same_as_none(self):
        assert trace_usage_totals({}, llm_tokens_fallback=5) == TraceUsage(total_tokens=5)
        assert trace_usage_totals({"costs": {}}, llm_tokens_fallback=5) == TraceUsage(
            total_tokens=5
        )

    def test_reports_no_cost_rather_than_a_zero_one(self):
        """An absent cost is how a caller tells 'not priced' from 'cost nothing'."""
        usage = trace_usage_totals(None, llm_tokens_fallback=420)

        assert usage.models == []
        assert usage.total_cost_usd is None
        assert usage.priced is False


@pytest.mark.unit
class TestMixedPricing:
    """One priced model beside one that LiteLLM cannot price."""

    def test_keeps_the_tokens_of_the_unpriced_model(self):
        blob = {
            "costs": {
                "total_cost_usd": 0.023,
                "total_input_tokens": 300,
                "total_output_tokens": 120,
                "total_tokens": 420,
                "breakdown": [
                    breakdown_entry("a", "gpt-4", 200, 100, 0.015, 0.008),
                    breakdown_entry("b", "self-hosted-7b", 100, 20, 0.0, 0.0),
                ],
            }
        }

        usage = trace_usage_totals(blob)

        assert usage.total_tokens == 420
        assert usage.models == ["gpt-4", "self-hosted-7b"]
        assert usage.providers == ["openai", "unknown"]
        assert usage.total_cost_usd == pytest.approx(0.023)


@pytest.mark.unit
class TestModelsPairWithTheirOwnProviders:
    """models[0] and providers[0] must describe one model, and match the sort key.

    The grid renders them as "providers[0]/models[0]", and the list orders by the
    alphabetically first model. Derive the two lists independently and both break: the
    label names a provider that served a different model, and the row sits where one
    model belongs while its cell reads another.
    """

    def blob(self, *pairs):
        return {
            "costs": {
                "total_cost_usd": 0.03,
                "breakdown": [
                    breakdown_entry(f"s{i}", model, 10, 5, 0.01, 0.005, provider)
                    for i, (model, provider) in enumerate(pairs)
                ],
            }
        }

    def test_models_come_back_alphabetically(self):
        """Which is what trace_first_model_expr orders by in SQL."""
        usage = trace_usage_totals(self.blob(("gpt-4", "openai"), ("alpha", "gemini")))

        assert usage.models == ["alpha", "gpt-4"]

    def test_the_first_provider_serves_the_first_model(self):
        usage = trace_usage_totals(self.blob(("gpt-4", "openai"), ("alpha", "gemini")))

        assert usage.providers[0] == "gemini"

    def test_a_provider_that_sorts_the_other_way_still_pairs(self):
        """alpha is on openai, beta on gemini: sorting each list alone reverses them."""
        usage = trace_usage_totals(self.blob(("alpha", "openai"), ("beta", "gemini")))

        assert usage.models[0] == "alpha"
        assert usage.providers[0] == "openai"

    def test_providers_are_still_deduped_for_counting(self):
        usage = trace_usage_totals(
            self.blob(("alpha", "openai"), ("beta", "openai"), ("gamma", "gemini"))
        )

        assert usage.models == ["alpha", "beta", "gamma"]
        assert usage.providers == ["openai", "gemini"]


@pytest.mark.unit
class TestZeroCostIsNotUnknown:
    """A model priced at zero costs a knowable nothing; only an unpriced trace is unknown."""

    def test_a_free_model_reports_its_zero(self):
        blob = {
            "costs": {
                "total_cost_usd": 0.0,
                "breakdown": [breakdown_entry("a", "free-tier", 100, 50, 0.0, 0.0, "gemini")],
            }
        }

        row = trace_summary_usage(blob, 0)

        assert row["total_cost_usd"] == 0.0
        assert row["total_input_cost_usd"] == 0.0
        assert row["models"] == ["free-tier"]

    def test_an_unpriced_trace_still_reports_nothing(self):
        row = trace_summary_usage(None, llm_tokens_fallback=420)

        assert row["total_cost_usd"] is None
        assert row["total_input_cost_usd"] is None
        assert row["models"] == []

    def test_tokens_survive_when_cost_is_unknown(self):
        """Tokens have a pre-enrichment fallback; hiding them with cost would lose it."""
        row = trace_summary_usage(None, llm_tokens_fallback=420)

        assert row["total_tokens"] == 420


def unpriced_entry(span_id, model, input_tokens, output_tokens):
    """One span enrichment could not price: tokens and a model name, no cost keys.

    Written this way because the enrichment processor dumps with ``exclude_none``, so a
    cost of None is not a null in the blob, it is an absent key.
    """
    return {
        "span_id": span_id,
        "model_name": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


@pytest.mark.unit
class TestNothingCouldBePriced:
    """A self-hosted model, or one newer than the bundled price list.

    Its tokens and its name are known; its price is not. Reporting zero here is what
    made a run on a private deployment read as a free run.
    """

    def blob(self):
        return {
            "costs": {
                "total_input_tokens": 300,
                "total_output_tokens": 120,
                "total_tokens": 420,
                "breakdown": [unpriced_entry("a", "my-self-hosted-llama", 300, 120)],
            }
        }

    def test_the_cost_is_unknown_rather_than_zero(self):
        usage = trace_usage_totals(self.blob())

        assert usage.total_cost_usd is None
        assert usage.input_cost_usd is None
        assert usage.output_cost_usd is None
        assert usage.priced is False

    def test_the_tokens_and_the_model_survive(self):
        usage = trace_usage_totals(self.blob())

        assert usage.total_tokens == 420
        assert usage.models == ["my-self-hosted-llama"]

    def test_the_list_row_shows_a_dash_not_a_zero(self):
        row = trace_summary_usage(self.blob(), 0)

        assert row["total_cost_usd"] is None
        assert row["total_input_cost_usd"] is None
        assert row["total_tokens"] == 420
        # Naming the model is not the same as having priced it, which is the
        # assumption that let an unpriceable run render a confident zero.
        assert row["models"] == ["my-self-hosted-llama"]

    def test_a_mixed_trace_reports_only_the_priced_half(self):
        blob = {
            "costs": {
                "total_tokens": 540,
                "breakdown": [
                    breakdown_entry("a", "gpt-4", 200, 100, 0.015, 0.008),
                    unpriced_entry("b", "my-self-hosted-llama", 100, 20),
                ],
            }
        }

        row = trace_summary_usage(blob, 0)

        assert row["total_cost_usd"] == pytest.approx(0.023)
        assert row["models"] == ["gpt-4", "my-self-hosted-llama"]


@pytest.mark.unit
class TestOneModelServedByTwoProviders:
    """The same model name can arrive from two providers in one trace.

    gpt-4o through both openai and azure, say, or a run that failed over. Keying the
    pairs on the model alone keeps whichever provider was seen first and drops the other,
    which would quietly narrow any filter built on the provider list.
    """

    def blob(self, *pairs):
        return {
            "costs": {
                "total_cost_usd": 0.03,
                "breakdown": [
                    breakdown_entry(f"s{i}", model, 10, 5, 0.01, 0.005, provider)
                    for i, (model, provider) in enumerate(pairs)
                ],
            }
        }

    def test_keeps_both_providers(self):
        usage = trace_usage_totals(self.blob(("gpt-4o", "openai"), ("gpt-4o", "azure")))

        assert usage.providers == ["azure", "openai"]

    def test_still_lists_the_model_once(self):
        usage = trace_usage_totals(self.blob(("gpt-4o", "openai"), ("gpt-4o", "azure")))

        assert usage.models == ["gpt-4o"]

    def test_the_label_still_names_a_provider_that_served_it(self):
        usage = trace_usage_totals(self.blob(("gpt-4o", "openai"), ("gpt-4o", "azure")))

        assert usage.providers[0] in {"openai", "azure"}
        assert usage.models[0] == "gpt-4o"
