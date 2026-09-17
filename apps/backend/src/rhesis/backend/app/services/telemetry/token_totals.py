"""Trace-level token totals.

One definition of "how many tokens did this trace use", shared by every read path
so the traces list, the trace detail drawer, the test-run trace list and the
project metrics endpoint can never disagree again.
"""

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

from rhesis.backend.app.constants import AISpanAttributes, EnrichedDataKeys
from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.services.telemetry.providers import resolve_provider

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
        # deriving it from input + output would quietly discard those. A zero total
        # next to non-zero input or output is contradictory, so treat it as missing.
        totals[2] += (
            input_tokens + output_tokens
            if reported_total is None or int(reported_total) == 0
            else int(reported_total)
        )

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


@dataclass(frozen=True)
class TraceUsage:
    """Everything one trace spent: tokens, the cost of each half, and what served it.

    Zeros here mean "nothing was recorded", which for cost is indistinguishable from
    "nothing was priced" -- callers that need to tell those apart should check
    ``models`` instead, which is empty only when the trace has no priced LLM spans at all.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    total_cost_eur: float = 0.0
    models: List[str] = field(default_factory=list)
    providers: List[str] = field(default_factory=list)


def _distinct_in_order(values: Iterable[Optional[str]]) -> List[str]:
    """Dedupe while keeping first-seen order, matching how enrichment writes its lists."""
    return list(dict.fromkeys(str(value) for value in values if value))


def model_provider_pairs(breakdown: Sequence[dict]) -> List[Tuple[str, str]]:
    """Distinct (model, provider) pairs from a cost breakdown, ordered by model name.

    Ordered rather than merely deduped, for two reasons that both bite at index 0.

    The list orders by ``trace_first_model_expr``, which is ``MIN(model_name)`` in SQL.
    Sorting here is what makes ``models[0]`` the same model the ordering used, so a row
    does not sit where "alpha-model" belongs while its cell reads "gpt-4".

    And the provider has to travel with its own model. Deriving the two lists separately
    and sorting each -- which is what this replaces -- pairs the alphabetically first
    model with the alphabetically first provider, which are routinely different rows:
    alpha-model on openai beside beta-model on gemini renders as "gemini/alpha-model".

    Only index 0 is guaranteed to correspond once the provider list is deduped, which is
    all any caller pairs; the rest are for counting and filtering.
    """
    by_model: dict = {}
    for entry in breakdown:
        model = entry.get(EnrichedDataKeys.MODEL_NAME)
        if not model:
            continue
        model = str(model)
        if model not in by_model:
            by_model[model] = entry.get(EnrichedDataKeys.PROVIDER) or resolve_provider(None, model)
    return [(model, by_model[model]) for model in sorted(by_model)]


def _tokens_from_breakdown(
    breakdown: Sequence[dict], llm_tokens_fallback: int
) -> Tuple[int, int, int]:
    """Token split for a blob written before the trace-level token fields existed.

    The per-span breakdown has carried input_tokens and output_tokens since the first
    version of enrichment, so an old blob can still report its split rather than zeros.
    ``total_tokens`` per span is newer, hence the fall back to input + output, and to the
    SQL figure when the breakdown is empty too.
    """
    if not breakdown:
        return 0, 0, llm_tokens_fallback

    input_tokens = sum(int(entry.get(EnrichedDataKeys.INPUT_TOKENS, 0) or 0) for entry in breakdown)
    output_tokens = sum(
        int(entry.get(EnrichedDataKeys.OUTPUT_TOKENS, 0) or 0) for entry in breakdown
    )
    total_tokens = sum(
        int(entry.get(EnrichedDataKeys.TOTAL_TOKENS, 0) or 0)
        or int(entry.get(EnrichedDataKeys.INPUT_TOKENS, 0) or 0)
        + int(entry.get(EnrichedDataKeys.OUTPUT_TOKENS, 0) or 0)
        for entry in breakdown
    )
    return input_tokens, output_tokens, total_tokens


def trace_usage_totals(enriched_data: Optional[dict], llm_tokens_fallback: int = 0) -> TraceUsage:
    """Full usage for one trace, reading whatever the enrichment blob happens to carry.

    Deliberately tolerant of older blobs. The trace-level input/output cost split and the
    model and provider lists were added after enrichment had already run over a lot of
    traces, so when those keys are missing they are derived from ``costs.breakdown``,
    which has carried the same figures per span from the start. That is what makes this
    safe to ship without a backfill: an un-re-enriched trace reports the same numbers it
    will report once it is re-enriched.

    ``llm_tokens_fallback`` is the SQL token sum for traces enrichment has not reached at
    all, the same figure ``trace_summary_totals`` takes.
    """
    costs = (enriched_data or {}).get(EnrichedDataKeys.COSTS) or {}
    if not costs:
        return TraceUsage(total_tokens=llm_tokens_fallback)

    breakdown = costs.get(EnrichedDataKeys.BREAKDOWN) or []

    tokens = token_totals_from_enriched(enriched_data)
    if tokens is None:
        tokens = _tokens_from_breakdown(breakdown, llm_tokens_fallback)

    input_cost = costs.get(EnrichedDataKeys.TOTAL_INPUT_COST_USD)
    output_cost = costs.get(EnrichedDataKeys.TOTAL_OUTPUT_COST_USD)
    if input_cost is None or output_cost is None:
        input_cost = sum(
            float(entry.get(EnrichedDataKeys.INPUT_COST_USD, 0.0) or 0.0) for entry in breakdown
        )
        output_cost = sum(
            float(entry.get(EnrichedDataKeys.OUTPUT_COST_USD, 0.0) or 0.0) for entry in breakdown
        )

    # Always from the breakdown, never from the blob's own models_used/providers_used:
    # those are two independent lists, and pairing a model with a provider needs them to
    # have come from the same entry. An entry with no provider falls back to what its
    # model implies, the same answer re-enrichment would reach for a span that stamped
    # nothing.
    pairs = model_provider_pairs(breakdown)
    models = [model for model, _ in pairs]
    providers = _distinct_in_order(provider for _, provider in pairs)

    return TraceUsage(
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        total_tokens=tokens[2],
        input_cost_usd=round(float(input_cost or 0.0), 6),
        output_cost_usd=round(float(output_cost or 0.0), 6),
        total_cost_usd=float(costs.get(EnrichedDataKeys.TOTAL_COST_USD, 0.0) or 0.0),
        total_cost_eur=float(costs.get(EnrichedDataKeys.TOTAL_COST_EUR, 0.0) or 0.0),
        models=list(models),
        providers=list(providers),
    )


def trace_summary_usage(enriched_data: Optional[dict], llm_tokens_fallback: int) -> dict:
    """The usage fields of a trace list row, ready to splat into a ``TraceSummary``.

    Both list endpoints -- the traces page and a test run's traces tab -- build the same
    row from the same ``query_traces`` output, and each had its own copy of this
    unpacking. One copy so a field added here reaches both.

    Zero becomes ``None`` for every figure, which is the convention the list response
    already used for tokens and cost: the grid renders a dash for an absent number rather
    than a zero it cannot vouch for. ``models`` stays a list, empty when the trace has
    nothing priced, since that is what tells "not traced" from "traced and free".
    """
    usage = trace_usage_totals(enriched_data, llm_tokens_fallback)
    priced = bool(usage.models)

    def tokens(value):
        """Zero tokens is nothing to show, and tokens have a pre-enrichment fallback."""
        return value or None

    def cost(value):
        """Keyed off whether the trace was priced at all, not off the number.

        A model LiteLLM prices at zero -- a free tier, a comped deployment -- costs a
        real, knowable nothing, and showing a dash for it would claim we had no idea.
        Only a trace nothing priced gets the dash.
        """
        return value if priced else None

    return {
        "total_tokens": tokens(usage.total_tokens),
        "total_input_tokens": tokens(usage.input_tokens),
        "total_output_tokens": tokens(usage.output_tokens),
        "total_cost_usd": cost(usage.total_cost_usd),
        "total_cost_eur": cost(usage.total_cost_eur),
        "total_input_cost_usd": cost(usage.input_cost_usd),
        "total_output_cost_usd": cost(usage.output_cost_usd),
        "models": usage.models,
        "providers": usage.providers,
    }
