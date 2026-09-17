"""SQL for the token and cost figures that live in trace JSONB.

Tokens sit in ``Trace.attributes`` per span; costs sit in ``Trace.enriched_data``, which
``mark_trace_processed`` writes onto *every* span row of the trace. Anything that sums the
enriched blob across span rows multiplies it by the span count, so every read collapses to
one row per ``trace_id`` first -- that is what ``per_trace_usage_subquery`` is for.

One copy of these expressions, because the traces list, the metrics rollup and the
test-run rollup have to produce the same number for the same trace or the UI contradicts
itself.
"""

from typing import Any, Optional, Sequence

from sqlalchemy import and_, case, column, false, func, literal, or_, select, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from rhesis.backend.app.constants import AISpanAttributes, EnrichedDataKeys


def is_llm_invoke(attributes) -> Any:
    """Predicate for the only spans that carry countable usage.

    Agent-run spans repeat their children's tokens as an aggregate and embedding spans
    carry tokens enrichment never priced, so both are excluded -- the same filter
    ``calculate_token_costs`` applies, which is what keeps SQL and Python agreeing.
    """
    return (
        attributes[AISpanAttributes.OPERATION_TYPE].as_string()
        == AISpanAttributes.OPERATION_LLM_INVOKE
    )


def span_token_expr(attributes, key: str) -> Any:
    """One side of a span's token count, as a float, defaulting to zero."""
    return func.coalesce(attributes[key].as_float(), 0.0)


def span_total_tokens_expr(attributes) -> Any:
    """Per-span token total in SQL, matching ``_span_token_counts`` in enrichment/core.py.

    Falls back to ``input + output`` when no total was reported, and treats a reported
    zero as missing when either side is non-zero. That combination is contradictory and
    only reachable through hand-set OTLP attributes or ``create_llm_attributes`` with a
    single side, never through a shipped integration; trusting the zero would undercount.

    Each side is coalesced separately because ``NULL + 100`` is ``NULL`` in SQL, which
    would otherwise drop a span that reported only one of the two.
    """
    return func.coalesce(
        func.nullif(attributes[AISpanAttributes.TOKENS_TOTAL].as_float(), 0.0),
        span_token_expr(attributes, AISpanAttributes.TOKENS_INPUT)
        + span_token_expr(attributes, AISpanAttributes.TOKENS_OUTPUT),
        0.0,
    )


def _llm_span_sum(attributes, value_expr) -> Any:
    """Sum *value_expr* over the llm.invoke spans only, zero when there are none."""
    return func.coalesce(func.sum(case((is_llm_invoke(attributes), value_expr), else_=0.0)), 0.0)


def _breakdown_entries(enriched_data, name: str):
    """The rows of a trace's cost breakdown, as a table-valued expression."""
    return func.jsonb_array_elements(
        enriched_data[EnrichedDataKeys.COSTS][EnrichedDataKeys.BREAKDOWN]
    ).table_valued(column("value", JSONB), name=name)


def _breakdown_sum(enriched_data, entry_value_expr) -> Any:
    """Sum a per-entry expression across ``costs.breakdown``, NULL when there are none.

    Every blob enriched before the trace-level rollup existed still carries the same
    figures per span, so deriving them here is what lets the new totals appear on
    existing traces without a backfill or a re-enrichment pass.

    NULL rather than zero for a trace with no breakdown, which matters: the caller
    coalesces this against the raw span sum, and a zero here would swallow that fallback
    and report an unenriched trace as having spent nothing.

    Only reached when the rolled-up key is NULL, since ``coalesce`` short-circuits -- so
    it stops costing anything once a trace has been enriched by a current worker.
    """
    entries = _breakdown_entries(enriched_data, "breakdown_entry")

    return (
        select(func.sum(entry_value_expr(entries.c.value))).select_from(entries).scalar_subquery()
    )


def enriched_cost_expr(
    enriched_data, rollup_key: str, breakdown_key: str, *, default: Optional[float] = 0.0
) -> Any:
    """A trace-level cost figure: the rolled-up total, else summed from the breakdown.

    ``default`` is where a trace neither figure knows about lands. Zero suits a rollup,
    which sums many traces and wants a number for each. ``None`` suits ordering a list of
    single traces, where an unpriced one should read as unknown and sink under
    ``nullslast`` rather than claim to have cost nothing -- which is also what the list
    response shows for it, a dash rather than a zero.
    """
    fallbacks = [
        enriched_data[EnrichedDataKeys.COSTS][rollup_key].as_float(),
        _breakdown_sum(enriched_data, lambda entry: entry[breakdown_key].as_float()),
    ]
    if default is not None:
        fallbacks.append(default)
    return func.coalesce(*fallbacks)


def distinct_breakdown_pairs(db: Session, base) -> list:
    """Distinct (model name, provider exactly as recorded) pairs across the scope.

    Read from ``costs.breakdown`` and not from span attributes, because the breakdown is
    what the row displays and a filter has to agree with the thing beside it. The two
    genuinely differ: on the dev instance, spans stamp ``openai`` on a gemini-2.5-flash
    call while the breakdown entries for that model carry no provider at all, so the row
    shows gemini. Filtering on the attributes returned traces whose Model column said
    something else.

    The recorded provider is usually NULL -- it arrived after enrichment had already run
    over everything -- and those are placed from the model name by the caller, which
    needs LiteLLM.
    """
    entries = _breakdown_entries(base.c.enriched_data, "provider_scope")
    model = entries.c.value[EnrichedDataKeys.MODEL_NAME].as_string()
    recorded = entries.c.value[EnrichedDataKeys.PROVIDER].as_string()

    return db.execute(
        select(model.label("model_name"), recorded.label("recorded"))
        .select_from(base)
        .join(entries, true())
        .where(model.isnot(None))
        .distinct()
    ).all()


def provider_breakdown_clause(enriched_data, recorded: Sequence[str], models: Sequence[str]) -> Any:
    """Match a trace whose breakdown holds an entry served by one of the providers.

    Two halves, because a provider reaches an entry two ways. An entry that recorded one
    is matched on that, which wins outright -- the same precedence ``resolve_provider``
    applies, so an entry whose provider its model name would not imply still lands where
    it was recorded. An entry that recorded nothing is matched on its model name, having
    been placed by LiteLLM beforehand.

    The recorded value must be NULL on the second half, not merely different: without
    that, an entry recorded as ``azure`` would also match a filter for ``openai`` purely
    because its model is an OpenAI one, which is the disagreement the record settles.

    A trace enrichment has not reached has no breakdown and so matches nothing, which is
    right: its Model column is a dash for the same reason.
    """
    if not recorded and not models:
        # Nothing in scope resolves to what was asked for, so nothing matches.
        return false()

    entries = _breakdown_entries(enriched_data, "provider_match")
    model = entries.c.value[EnrichedDataKeys.MODEL_NAME].as_string()
    recorded_col = entries.c.value[EnrichedDataKeys.PROVIDER].as_string()

    clauses = []
    if recorded:
        clauses.append(recorded_col.in_(list(recorded)))
    if models:
        clauses.append(and_(recorded_col.is_(None), model.in_(list(models))))

    return select(literal(1)).select_from(entries).where(or_(*clauses)).exists()


def trace_first_model_expr(enriched_data) -> Any:
    """One trace's alphabetically first priced model, NULL when it has none.

    Read from ``costs.breakdown`` rather than ``costs.models_used``, because the
    breakdown has been there since the first version of enrichment while ``models_used``
    arrived later -- and one is derived from the other, so they never disagree.

    Ordering a list by "model" has to pick one for a trace that used several; first
    alphabetically is the one the grid cell already shows before its "+N".
    """
    entries = func.jsonb_array_elements(
        enriched_data[EnrichedDataKeys.COSTS][EnrichedDataKeys.BREAKDOWN]
    ).table_valued(column("value", JSONB), name="model_entry")

    return (
        select(func.min(entries.c.value[EnrichedDataKeys.MODEL_NAME].as_string()))
        .select_from(entries)
        .scalar_subquery()
    )


def _breakdown_entry_total_tokens(entry) -> Any:
    """One breakdown entry's token total, matching ``_span_token_counts``.

    Trusts the reported total and falls back to input + output, which is what an entry
    written before per-span totals existed needs.
    """
    return func.coalesce(
        func.nullif(entry[EnrichedDataKeys.TOTAL_TOKENS].as_float(), 0.0),
        func.coalesce(entry[EnrichedDataKeys.INPUT_TOKENS].as_float(), 0.0)
        + func.coalesce(entry[EnrichedDataKeys.OUTPUT_TOKENS].as_float(), 0.0),
        0.0,
    )


def enriched_token_expr(enriched_data, rollup_key: str, breakdown_key: str) -> Any:
    """A trace-level token figure: the rolled-up total, else summed from the breakdown.

    The breakdown step is what keeps this in step with ``trace_usage_totals``, which
    derives the same figures in Python. Without it the two disagree for a blob that has
    a breakdown but no trace-level token totals -- and they disagree worst exactly where
    it is hardest to notice, under ``test_run_id`` scope, where the llm.invoke spans the
    raw fallback sums are not in scope at all because only the root span carries the run.

    Stays NULL when neither source knows, so the caller can still fall back to the raw
    span sum for a trace enrichment has not reached.
    """
    return func.coalesce(
        enriched_data[EnrichedDataKeys.COSTS][rollup_key].as_float(),
        _breakdown_sum(
            enriched_data,
            _breakdown_entry_total_tokens
            if breakdown_key == EnrichedDataKeys.TOTAL_TOKENS
            else (lambda entry: entry[breakdown_key].as_float()),
        ),
    )


def per_trace_usage_subquery(db: Session, base, *, extra_group_by: Sequence = ()) -> Any:
    """Collapse a scanned set of span rows to one usage row per trace.

    ``MAX`` is exact for the enriched columns precisely because every span row of a trace
    carries the identical blob. The ``raw_*`` columns are the pre-enrichment fallback,
    summed over llm.invoke spans only, so a trace ingested seconds ago reports the token
    figure it will keep once enrichment lands. Cost has no such fallback: it cannot be
    derived from span attributes.

    Args:
        base: a subquery over ``trace`` already narrowed to the caller's scope.
        extra_group_by: further columns to carry through and group by alongside
            ``trace_id``, so a caller can roll the collapsed traces up again -- per test
            run, say. Must be functionally dependent on the trace, which ``test_run_id``
            is, or the collapse would split one trace across several rows.
    """
    attributes = base.c.attributes
    enriched = base.c.enriched_data

    def enriched_tokens(rollup_key: str, breakdown_key: str):
        return func.max(enriched_token_expr(enriched, rollup_key, breakdown_key))

    return (
        db.query(
            *extra_group_by,
            base.c.trace_id.label("trace_id"),
            enriched_tokens(EnrichedDataKeys.TOTAL_TOKENS, EnrichedDataKeys.TOTAL_TOKENS).label(
                "enriched_tokens"
            ),
            enriched_tokens(
                EnrichedDataKeys.TOTAL_INPUT_TOKENS, EnrichedDataKeys.INPUT_TOKENS
            ).label("enriched_input_tokens"),
            enriched_tokens(
                EnrichedDataKeys.TOTAL_OUTPUT_TOKENS, EnrichedDataKeys.OUTPUT_TOKENS
            ).label("enriched_output_tokens"),
            # Same breakdown fallback as the two halves below. Without it a blob that
            # carries a breakdown but no trace-level total reports zero cost beside a
            # non-zero input and output cost -- three figures from one trace that do not
            # add up.
            func.max(
                enriched_cost_expr(
                    enriched,
                    EnrichedDataKeys.TOTAL_COST_USD,
                    EnrichedDataKeys.TOTAL_COST_USD,
                )
            ).label("cost_usd"),
            func.max(
                enriched_cost_expr(
                    enriched,
                    EnrichedDataKeys.TOTAL_INPUT_COST_USD,
                    EnrichedDataKeys.INPUT_COST_USD,
                )
            ).label("input_cost_usd"),
            func.max(
                enriched_cost_expr(
                    enriched,
                    EnrichedDataKeys.TOTAL_OUTPUT_COST_USD,
                    EnrichedDataKeys.OUTPUT_COST_USD,
                )
            ).label("output_cost_usd"),
            _llm_span_sum(attributes, span_total_tokens_expr(attributes)).label("raw_tokens"),
            _llm_span_sum(
                attributes, span_token_expr(attributes, AISpanAttributes.TOKENS_INPUT)
            ).label("raw_input_tokens"),
            _llm_span_sum(
                attributes, span_token_expr(attributes, AISpanAttributes.TOKENS_OUTPUT)
            ).label("raw_output_tokens"),
        )
        .group_by(*extra_group_by, base.c.trace_id)
        .subquery()
    )


def models_used_select(base, *, extra_columns: Sequence = ()) -> Any:
    """Distinct (model, reported provider) pairs over a scanned set of span rows.

    Reads the enrichment breakdown *and* raw span attributes, because neither alone
    covers every case. Scoping by test run is the reason: ``test_run_id`` is stamped on
    the root span only, so a run's llm.invoke children are not in ``base`` at all and the
    attribute source finds nothing. The enriched blob is on every span row of the trace,
    including that root, so it answers where attributes cannot. Attributes in turn answer
    for a trace enrichment has not reached yet, which has no blob.

    The provider comes back as reported and is NULL for anything that stamped none --
    older breakdown entries never carried one. The caller finishes the job with
    ``resolve_provider``, since deriving a provider from a model name is a LiteLLM
    lookup, not something SQL can do.

    ``extra_columns`` are selected ahead of the pair in both branches, so a caller can
    group the result by something wider -- per test run, say.
    """
    entries = func.jsonb_array_elements(
        base.c.enriched_data[EnrichedDataKeys.COSTS][EnrichedDataKeys.BREAKDOWN]
    ).table_valued(column("value", JSONB), name="breakdown_entry")

    enriched_model = entries.c.value[EnrichedDataKeys.MODEL_NAME].as_string()
    enriched_provider = entries.c.value[EnrichedDataKeys.PROVIDER].as_string()
    from_enrichment = (
        select(
            *extra_columns,
            enriched_model.label("model_name"),
            enriched_provider.label("provider"),
        )
        .select_from(base)
        .join(entries, true())
        .where(enriched_model.isnot(None))
        .distinct()
    )

    attributes = base.c.attributes
    span_model = attributes[AISpanAttributes.MODEL_NAME].as_string()
    span_provider = attributes[AISpanAttributes.MODEL_PROVIDER].as_string()
    from_attributes = (
        select(
            *extra_columns,
            span_model.label("model_name"),
            span_provider.label("provider"),
        )
        .select_from(base)
        .where(is_llm_invoke(attributes), span_model.isnot(None))
        .distinct()
    )

    return from_enrichment.union(from_attributes)


def models_used_rows(db: Session, base, *, extra_columns: Sequence = ()) -> list:
    """Execute :func:`models_used_select`. Sorting nests the selectable instead."""
    return db.execute(models_used_select(base, extra_columns=extra_columns)).all()


def coalesced_tokens(per_trace) -> Any:
    """Trace tokens as the response reports them: enriched when priced, raw until then."""
    return func.coalesce(per_trace.c.enriched_tokens, per_trace.c.raw_tokens, 0)


def coalesced_input_tokens(per_trace) -> Any:
    return func.coalesce(per_trace.c.enriched_input_tokens, per_trace.c.raw_input_tokens, 0)


def coalesced_output_tokens(per_trace) -> Any:
    return func.coalesce(per_trace.c.enriched_output_tokens, per_trace.c.raw_output_tokens, 0)


__all__ = [
    "coalesced_input_tokens",
    "coalesced_output_tokens",
    "coalesced_tokens",
    "enriched_cost_expr",
    "enriched_token_expr",
    "is_llm_invoke",
    "distinct_breakdown_pairs",
    "models_used_rows",
    "models_used_select",
    "per_trace_usage_subquery",
    "provider_breakdown_clause",
    "span_token_expr",
    "span_total_tokens_expr",
    "trace_first_model_expr",
]
