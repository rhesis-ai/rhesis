"""Tests for trace_usage_totals.

The accessor that reports what a trace spent. Its job is to answer the same way for a
blob written by a current worker and one written before the trace-level input/output
split existed, so the new figures appear on traces already in the database without a
backfill or a re-enrichment pass.
"""

import pytest

from rhesis.backend.app.services.telemetry.token_totals import TraceUsage, trace_usage_totals


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
        usage = trace_usage_totals(legacy_blob())

        assert usage.models == ["gpt-4", "gemini-2.0-flash"]

    def test_derives_providers_from_the_model_names(self):
        """No entry carries a provider, so each is placed from its model."""
        usage = trace_usage_totals(legacy_blob())

        assert usage.providers == ["openai", "gemini"]

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

    def test_reports_no_models_rather_than_a_zero_cost(self):
        """Empty models is how a caller tells 'not priced yet' from 'cost nothing'."""
        usage = trace_usage_totals(None, llm_tokens_fallback=420)

        assert usage.models == []
        assert usage.total_cost_usd == 0.0


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
