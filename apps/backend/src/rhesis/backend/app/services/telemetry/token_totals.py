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


def trace_cost_usd(enriched_data: Optional[dict]) -> Optional[float]:
    """Trace-level cost in USD, or ``None`` when there is no figure to report.

    Unlike tokens, cost has no fallback: it cannot be derived from span attributes.
    ``None`` covers both silences -- enrichment has not run, and it ran but could not
    price a single model -- and a caller that shows a zero for either claims the run
    was free.
    """
    costs = (enriched_data or {}).get(EnrichedDataKeys.COSTS) or {}
    total = costs.get(EnrichedDataKeys.TOTAL_COST_USD)
    return None if total is None else float(total)


def trace_summary_totals(
    enriched_data: Optional[dict], llm_tokens_fallback: int
) -> Tuple[int, int, int, Optional[float], Optional[float]]:
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

    Either cost is ``None`` when the trace carries no figure -- not enriched, or
    enriched and nothing on it could be priced. Zero is reserved for a trace that was
    priced and came to nothing.

    Returns:
        ``(input_tokens, output_tokens, total_tokens, cost_usd, cost_eur)``
    """
    costs = (enriched_data or {}).get(EnrichedDataKeys.COSTS) or {}

    enriched = token_totals_from_enriched(enriched_data)
    if enriched is None:
        input_tokens, output_tokens, total_tokens = 0, 0, llm_tokens_fallback
    else:
        input_tokens, output_tokens, total_tokens = enriched

    def cost(key: str) -> Optional[float]:
        value = costs.get(key)
        return None if value is None else float(value)

    return (
        input_tokens,
        output_tokens,
        total_tokens,
        cost(EnrichedDataKeys.TOTAL_COST_USD),
        cost(EnrichedDataKeys.TOTAL_COST_EUR),
    )


@dataclass(frozen=True)
class TraceUsage:
    """Everything one trace spent: tokens, the cost of each half, and what served it.

    A cost of ``None`` means nothing on the trace could be priced -- no rate for the
    model, or no model name on the span. A cost of zero means the trace was priced and
    came to nothing, which is a real, knowable figure. ``models`` cannot tell the two
    apart: an unpriceable span still reports the model it used.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: Optional[float] = None
    output_cost_usd: Optional[float] = None
    total_cost_usd: Optional[float] = None
    total_cost_eur: Optional[float] = None
    models: List[str] = field(default_factory=list)
    providers: List[str] = field(default_factory=list)

    @property
    def priced(self) -> bool:
        """Whether anything on this trace carries a cost somebody computed."""
        return self.total_cost_usd is not None


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

    Keyed on the pair rather than on the model, because one model name can be served by
    more than one provider in a single trace -- the same gpt-4o reached through both
    openai and azure. Keying on the model alone would keep whichever provider was seen
    first and drop the other from the provider list, quietly narrowing a filter built on
    it.
    """
    pairs = set()
    for entry in breakdown:
        model = entry.get(EnrichedDataKeys.MODEL_NAME)
        if not model:
            continue
        model = str(model)
        provider = entry.get(EnrichedDataKeys.PROVIDER) or resolve_provider(None, model)
        pairs.add((model, provider))
    return sorted(pairs)


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


def _rounded(value: Optional[float]) -> Optional[float]:
    """Round a cost, leaving an absent one absent."""
    return None if value is None else round(float(value), 6)


def _breakdown_cost(breakdown: Sequence[dict], key: str) -> Optional[float]:
    """Sum one cost field over the breakdown entries that carry it.

    ``None`` when not one of them does. That is the shape the SQL side already has --
    ``SUM`` over all-NULL is NULL -- and keeping them the same is what stops the cell
    and the sort disagreeing about a trace nothing could price.
    """
    priced = [float(entry[key]) for entry in breakdown if entry.get(key) is not None]
    return sum(priced) if priced else None


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
        input_cost = _breakdown_cost(breakdown, EnrichedDataKeys.INPUT_COST_USD)
        output_cost = _breakdown_cost(breakdown, EnrichedDataKeys.OUTPUT_COST_USD)

    # Always from the breakdown, never from the blob's own models_used/providers_used:
    # those are two independent lists, and pairing a model with a provider needs them to
    # have come from the same entry. An entry with no provider falls back to what its
    # model implies, the same answer re-enrichment would reach for a span that stamped
    # nothing.
    pairs = model_provider_pairs(breakdown)
    models = _distinct_in_order(model for model, _ in pairs)
    providers = _distinct_in_order(provider for _, provider in pairs)

    total_cost_usd = costs.get(EnrichedDataKeys.TOTAL_COST_USD)
    if total_cost_usd is None:
        total_cost_usd = _breakdown_cost(breakdown, EnrichedDataKeys.TOTAL_COST_USD)

    return TraceUsage(
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        total_tokens=tokens[2],
        input_cost_usd=_rounded(input_cost),
        output_cost_usd=_rounded(output_cost),
        total_cost_usd=_rounded(total_cost_usd),
        total_cost_eur=_rounded(costs.get(EnrichedDataKeys.TOTAL_COST_EUR)),
        models=list(models),
        providers=list(providers),
    )


def trace_summary_usage(enriched_data: Optional[dict], llm_tokens_fallback: int) -> dict:
    """The usage fields of a trace list row, ready to splat into a ``TraceSummary``.

    Both list endpoints -- the traces page and a test run's traces tab -- build the same
    row from the same ``query_traces`` output, and each had its own copy of this
    unpacking. One copy so a field added here reaches both.

    Zero tokens become ``None``, which is the convention the list response already used:
    the grid renders a dash for an absent number rather than a zero it cannot vouch for.
    A cost of zero is left alone, because a priced trace that came to nothing really did
    cost nothing; only a trace nothing could price reports no cost, and enrichment
    already recorded that as ``None``. ``models`` stays a list either way -- an
    unpriceable span still names the model it used.
    """
    usage = trace_usage_totals(enriched_data, llm_tokens_fallback)

    def tokens(value):
        """Zero tokens is nothing to show, and tokens have a pre-enrichment fallback."""
        return value or None

    def cost(value):
        """Keyed off whether the trace was priced at all, not off the number.

        A model LiteLLM prices at zero -- a free tier, a comped deployment -- costs a
        real, knowable nothing, and showing a dash for it would claim we had no idea.
        Only a trace nothing priced gets the dash.
        """
        return value if usage.priced else None

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
