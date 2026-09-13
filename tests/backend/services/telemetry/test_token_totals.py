"""Tests for trace-level token totals.

These cover the one definition of "how many tokens did this trace use" that the
traces list, the trace detail drawer, the test-run trace list and the project
metrics endpoint all share.
"""

from unittest.mock import Mock

import pytest
from rhesis.telemetry.attributes import AIAttributes

from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.services.telemetry.token_totals import (
    token_totals_from_enriched,
    token_totals_from_spans,
    trace_cost_usd,
    trace_summary_totals,
    trace_token_totals,
)


def llm_span(span_id, input_tokens, output_tokens, total=None, enriched=None):
    """An ``llm.invoke`` span -- the kind that carries countable usage."""
    attributes = {
        AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
        AIAttributes.MODEL_NAME: "gpt-4",
        AIAttributes.LLM_TOKENS_INPUT: input_tokens,
        AIAttributes.LLM_TOKENS_OUTPUT: output_tokens,
    }
    if total is not None:
        attributes[AIAttributes.LLM_TOKENS_TOTAL] = total
    return Mock(spec=Trace, span_id=span_id, attributes=attributes, enriched_data=enriched)


def enrichment(total_input, total_output, total, cost_usd=0.0, cost_eur=0.0):
    """An enriched_data blob shaped the way the enrichment service writes it."""
    return {
        "costs": {
            "total_cost_usd": cost_usd,
            "total_cost_eur": cost_eur,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total,
            "breakdown": [],
        }
    }


@pytest.mark.unit
class TestTokenTotalsFromSpans:
    """The pre-enrichment fallback, summed over llm.invoke spans."""

    def test_sums_llm_invoke_spans(self):
        spans = [llm_span("a", 100, 50, 150), llm_span("b", 200, 70, 270)]

        assert token_totals_from_spans(spans) == (300, 120, 420)

    def test_ignores_aggregated_agent_span(self):
        """The pydantic-ai double-count case.

        Its agent-run span repeats the aggregate of its children's usage under the
        same attribute keys, so a naive sum over every span would report 840.
        """
        agent_run = Mock(
            spec=Trace,
            span_id="agent-run",
            attributes={
                AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_AGENT_INVOKE,
                AIAttributes.LLM_TOKENS_INPUT: 300,
                AIAttributes.LLM_TOKENS_OUTPUT: 120,
                AIAttributes.LLM_TOKENS_TOTAL: 420,
            },
            enriched_data=None,
        )
        spans = [agent_run, llm_span("call-1", 100, 50, 150), llm_span("call-2", 200, 70, 270)]

        assert token_totals_from_spans(spans) == (300, 120, 420)

    def test_trusts_reported_total_over_derived(self):
        """Google ADK folds cache-read tokens into the reported total on purpose."""
        spans = [llm_span("adk", 100, 50, total=950)]

        assert token_totals_from_spans(spans) == (100, 50, 950)

    def test_derives_total_when_not_reported(self):
        spans = [llm_span("a", 100, 50)]

        assert token_totals_from_spans(spans) == (100, 50, 150)

    def test_no_llm_spans_is_zero_not_an_error(self):
        tool_span = Mock(
            spec=Trace,
            span_id="tool",
            attributes={AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE},
            enriched_data=None,
        )

        assert token_totals_from_spans([tool_span]) == (0, 0, 0)

    def test_span_with_no_attributes(self):
        bare = Mock(spec=Trace, span_id="bare", attributes=None, enriched_data=None)

        assert token_totals_from_spans([bare]) == (0, 0, 0)


@pytest.mark.unit
class TestTokenTotalsFromEnriched:
    """Reading the totals back out of the enrichment blob."""

    def test_reads_the_totals(self):
        assert token_totals_from_enriched(enrichment(300, 120, 420)) == (300, 120, 420)

    def test_unenriched_trace_is_unknown_not_zero(self):
        """None means "fall back", which is not the same as a confident zero."""
        assert token_totals_from_enriched(None) is None
        assert token_totals_from_enriched({}) is None
        assert token_totals_from_enriched({"costs": {}}) is None

    def test_blob_predating_the_token_fields_is_unknown(self):
        """An enrichment blob written before this change has costs but no tokens."""
        legacy = {"costs": {"total_cost_usd": 0.02, "total_cost_eur": 0.018, "breakdown": []}}

        assert token_totals_from_enriched(legacy) is None


@pytest.mark.unit
class TestTraceTokenTotals:
    """The detail endpoint's accessor: enrichment first, spans as fallback."""

    def test_prefers_enrichment(self):
        spans = [llm_span("a", 1, 1, 2, enriched=enrichment(300, 120, 420))]

        assert trace_token_totals(spans) == (300, 120, 420)

    def test_falls_back_to_spans_before_enrichment_runs(self):
        spans = [llm_span("a", 100, 50, 150), llm_span("b", 200, 70, 270)]

        assert trace_token_totals(spans) == (300, 120, 420)

    def test_both_paths_agree_for_the_same_spans(self):
        """The property that keeps the list and the drawer showing one number."""
        spans = [llm_span("a", 100, 50, 150), llm_span("b", 200, 70, 270)]
        from_spans = token_totals_from_spans(spans)

        enriched_spans = [
            llm_span("a", 100, 50, 150, enriched=enrichment(*from_spans)),
            llm_span("b", 200, 70, 270, enriched=enrichment(*from_spans)),
        ]

        assert trace_token_totals(enriched_spans) == from_spans

    def test_empty_span_set(self):
        assert trace_token_totals([]) == (0, 0, 0)


@pytest.mark.unit
class TestTraceSummaryTotals:
    """The list endpoints' accessor, which has one row rather than a span set."""

    def test_uses_enrichment_when_present(self):
        totals = trace_summary_totals(
            enrichment(300, 120, 420, cost_usd=0.02, cost_eur=0.018), llm_tokens_fallback=999
        )

        assert totals == (300, 120, 420, 0.02, 0.018)

    def test_uses_the_sql_fallback_before_enrichment_runs(self):
        """A freshly ingested trace still lists its tokens, and no cost yet."""
        totals = trace_summary_totals(None, llm_tokens_fallback=420)

        assert totals == (0, 0, 420, 0.0, 0.0)

    def test_no_llm_spans_reports_zero(self):
        assert trace_summary_totals(None, llm_tokens_fallback=0) == (0, 0, 0, 0.0, 0.0)


@pytest.mark.unit
class TestTraceCostUsd:
    """Cost has no fallback: it cannot be derived from span attributes."""

    def test_reads_the_enriched_cost(self):
        assert trace_cost_usd(enrichment(1, 1, 2, cost_usd=0.0123)) == 0.0123

    def test_unenriched_trace_is_zero(self):
        assert trace_cost_usd(None) == 0.0
        assert trace_cost_usd({}) == 0.0
