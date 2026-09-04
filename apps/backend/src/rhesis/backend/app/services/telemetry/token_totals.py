"""Trace-level token totals.

One definition of "how many tokens did this trace use", shared by every read path
so the traces list, the trace detail drawer, the test-run trace list and the
project metrics endpoint can never disagree again.
"""

from typing import Optional, Sequence, Tuple

from rhesis.backend.app.constants import AISpanAttributes, EnrichedDataKeys
from rhesis.backend.app.models.trace import Trace

# input, output, total
TokenTotals = Tuple[int, int, int]

ZERO_TOKENS: TokenTotals = (0, 0, 0)


def token_totals_from_enriched(enriched_data: Optional[dict]) -> Optional[TokenTotals]:
    """Trace-level input/output/total tokens from an enrichment blob.

    Returns ``None`` when the trace has not been enriched yet, which the caller
    should treat as "unknown" and fall back on — not as zero.

    Any span of the trace works as the source: ``mark_trace_processed`` writes the
    same trace-level blob onto every span row.
    """
    costs = (enriched_data or {}).get(EnrichedDataKeys.COSTS) or {}
    if not costs:
        return None

    # A pre-existing enrichment blob predates the token fields; treat it as unknown
    # so the caller falls back to the spans rather than reporting a confident zero.
    if EnrichedDataKeys.TOTAL_TOKENS not in costs:
        return None

    return (
        int(costs.get(EnrichedDataKeys.TOTAL_INPUT_TOKENS, 0) or 0),
        int(costs.get(EnrichedDataKeys.TOTAL_OUTPUT_TOKENS, 0) or 0),
        int(costs.get(EnrichedDataKeys.TOTAL_TOKENS, 0) or 0),
    )


def token_totals_from_spans(spans: Sequence[Trace]) -> TokenTotals:
    """Sum tokens over a trace's ``llm.invoke`` spans.

    The fallback for a trace whose enrichment has not run yet — it is dispatched
    asynchronously after ingest, so a trace opened immediately has no enriched
    data. The ``llm.invoke`` filter is the same one enrichment applies, which is
    what keeps the two paths agreeing: pydantic-ai reports aggregated usage on the
    agent-run span *and* per-call usage on its children, so summing every span
    would roughly double the real figure.
    """
    totals = [0, 0, 0]
    for span in spans:
        attributes = span.attributes or {}
        if attributes.get(AISpanAttributes.OPERATION_TYPE) != (
            AISpanAttributes.OPERATION_LLM_INVOKE
        ):
            continue
        input_tokens = int(attributes.get(AISpanAttributes.TOKENS_INPUT, 0) or 0)
        output_tokens = int(attributes.get(AISpanAttributes.TOKENS_OUTPUT, 0) or 0)
        reported_total = attributes.get(AISpanAttributes.TOKENS_TOTAL)
        totals[0] += input_tokens
        totals[1] += output_tokens
        # Trust the reported total; Google ADK folds cache-read tokens into it, so
        # deriving it from input + output would quietly discard those.
        totals[2] += input_tokens + output_tokens if reported_total is None else int(reported_total)

    return (totals[0], totals[1], totals[2])


def trace_token_totals(spans: Sequence[Trace]) -> TokenTotals:
    """Trace-level input/output/total tokens for a full span set.

    Prefers the enrichment breakdown and falls back to the spans themselves when
    enrichment has not run yet. Returns zeros for a trace with no LLM spans rather
    than raising.
    """
    if not spans:
        return ZERO_TOKENS

    enriched = token_totals_from_enriched(spans[0].enriched_data)
    if enriched is not None:
        return enriched

    return token_totals_from_spans(spans)


def trace_cost_usd(enriched_data: Optional[dict]) -> float:
    """Trace-level cost in USD, or 0.0 when the trace has not been enriched.

    Unlike tokens, cost has no fallback: it cannot be derived from span attributes.
    """
    costs = (enriched_data or {}).get(EnrichedDataKeys.COSTS) or {}
    return float(costs.get(EnrichedDataKeys.TOTAL_COST_USD, 0.0) or 0.0)


def trace_summary_totals(
    enriched_data: Optional[dict], llm_tokens_fallback: int
) -> Tuple[int, int, int, float, float]:
    """Token and cost totals for a trace list row.

    Shared by the traces list and the test-run trace list, which build the same
    ``TraceSummary`` from the same ``query_traces`` rows and each used to read
    tokens off the root span alone -- a span that is usually not an LLM span, so
    both reported zero.

    A list row is one span, not the whole trace, so the span-set fallback is not
    available here; ``llm_tokens_fallback`` is ``TraceRow.llm_tokens``, the same
    figure computed in SQL. The input/output split stays zero before enrichment:
    only the drawer shows it, and the drawer reads the detail endpoint, which has
    the full span set.

    Returns:
        ``(input_tokens, output_tokens, total_tokens, cost_usd, cost_eur)``
    """
    costs = (enriched_data or {}).get(EnrichedDataKeys.COSTS) or {}

    enriched = token_totals_from_enriched(enriched_data)
    if enriched is None:
        input_tokens, output_tokens, total_tokens = 0, 0, llm_tokens_fallback
    else:
        input_tokens, output_tokens, total_tokens = enriched

    return (
        input_tokens,
        output_tokens,
        total_tokens,
        float(costs.get(EnrichedDataKeys.TOTAL_COST_USD, 0.0) or 0.0),
        float(costs.get(EnrichedDataKeys.TOTAL_COST_EUR, 0.0) or 0.0),
    )
