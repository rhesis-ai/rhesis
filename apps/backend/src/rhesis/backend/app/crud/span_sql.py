"""SQL for the spans list: one row per span, filtered on the span itself or on its trace.

Some filters describe the trace, not the span. ``test_run_id`` and friends are stamped on
root spans only, and a multi-turn trace can have roots without a ``conversation_id``. So
those filters look at every row of the trace (matched by ``trace_id``); testing the row
itself would drop every child span.
"""

from typing import Any, Callable, Collection, List, Optional

from fastapi import HTTPException
from sqlalchemy import (
    Text,
    and_,
    any_,
    asc,
    case,
    column,
    desc,
    exists,
    false,
    func,
    literal,
    or_,
    select,
    type_coerce,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import aliased

from rhesis.backend.app import models
from rhesis.backend.app.constants import AISpanAttributes, EnrichedDataKeys, SpanType
from rhesis.backend.app.crud.usage_sql import span_total_tokens_expr
from rhesis.backend.app.schemas.telemetry import SpanFilters, TraceSource, TraceType

SPAN_SORT_FIELDS = frozenset({"start_time", "duration_ms", "span_name", "total_tokens", "cost_usd"})

# Filters a facet can leave out of span_filter_clauses, so it still lists every value.
SKIP_SPAN_TYPE = "span_type"
SKIP_SPAN_NAME = "span_name"
SKIP_MODEL = "model"
SKIP_AGENT = "agent"


def span_breakdown_entry() -> Any:
    """This span's entry in ``costs.breakdown``, NULL when it has none.

    Only llm.invoke spans are priced, so every other span skips the unnest.
    """
    trace = models.Trace
    entries = func.jsonb_array_elements(
        trace.enriched_data[EnrichedDataKeys.COSTS][EnrichedDataKeys.BREAKDOWN]
    ).table_valued(column("value", JSONB), name="span_entry")
    lookup = (
        select(entries.c.value)
        .select_from(entries)
        .where(entries.c.value[EnrichedDataKeys.SPAN_ID].as_string() == trace.span_id)
        .limit(1)
        .scalar_subquery()
    )
    return type_coerce(case((trace.span_type == SpanType.LLM_INVOKE, lookup)), JSONB)


def span_cost_expr(entry) -> Any:
    return entry[EnrichedDataKeys.TOTAL_COST_USD].as_float()


def span_model_expr(entry) -> Any:
    """The priced model, else the one the span reported -- what the span tree shows too."""
    return func.coalesce(
        entry[EnrichedDataKeys.MODEL_NAME].as_string(),
        models.Trace.attributes[AISpanAttributes.MODEL_NAME].as_string(),
    )


def span_recorded_provider_expr(entry) -> Any:
    """The provider as recorded, before ``resolve_provider`` fills gaps from the model.

    A priced span reads its breakdown entry even when that recorded nothing: attributes
    can stamp ``openai`` on a gemini call, and the traces list trusts the breakdown over
    them (see ``_provider_filter`` in crud/telemetry.py).
    """
    return case(
        (entry.isnot(None), entry[EnrichedDataKeys.PROVIDER].as_string()),
        else_=models.Trace.attributes[AISpanAttributes.MODEL_PROVIDER].as_string(),
    )


def span_token_columns() -> tuple:
    """(input, output, total) from span attributes; all NULL when it reported none."""
    attributes = models.Trace.attributes
    input_tokens = attributes[AISpanAttributes.TOKENS_INPUT].as_float()
    output_tokens = attributes[AISpanAttributes.TOKENS_OUTPUT].as_float()
    reported = or_(
        input_tokens.isnot(None),
        output_tokens.isnot(None),
        attributes[AISpanAttributes.TOKENS_TOTAL].as_float().isnot(None),
    )
    return input_tokens, output_tokens, case((reported, span_total_tokens_expr(attributes)))


#: The attributes holding a span's name, ahead of its span name: the SDK's ``targets.NAME_KEYS``.
SPAN_NAME_KEYS = (
    AISpanAttributes.TOOL_NAME,
    AISpanAttributes.AGENT_NAME,
    AISpanAttributes.MODEL_NAME,
)
#: What ``jsonb_typeof`` says of a JSON string.
JSONB_STRING = "string"


def span_name_field_expr(trace=models.Trace) -> Any:
    """The ``name`` a metric target reads, for *trace* (the table or an alias of it): the
    first of ``SPAN_NAME_KEYS`` that is a non-empty string, else the span name. Every query
    that reads a span's name builds it here."""

    def named(key: str) -> Any:
        value = trace.attributes.op("->")(literal(key, Text))
        as_text = trace.attributes.op("->>", return_type=Text)(literal(key, Text))
        is_string = func.jsonb_typeof(value) == JSONB_STRING
        return case((and_(is_string, as_text != ""), as_text))

    return func.coalesce(*(named(key) for key in SPAN_NAME_KEYS), trace.span_name)


def span_name_field_sql() -> str:
    """``span_name_field_expr`` as SQL text over the ``trace`` table, for raw statements."""
    compiled = span_name_field_expr().compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    return str(compiled)


def same_trace(other, trace) -> list:
    """*other* (an alias of the table) is a stored span of *trace*'s trace."""
    return [
        other.organization_id == trace.organization_id,
        other.project_id == trace.project_id,
        other.trace_id == trace.trace_id,
        other.deleted_at.is_(None),
    ]


def span_is_root_expr(trace=models.Trace) -> Any:
    """Whether *trace* is a root of its span tree: its parent isn't stored in the trace.

    Read from ``is_root``, which ingest keeps; a span stored before the column existed, and
    not backfilled yet, looks its parent up (``COALESCE`` reads that only for those rows)."""
    parent = aliased(models.Trace)
    stored_parent = exists().where(
        *same_trace(parent, trace), parent.span_id == trace.parent_span_id
    )
    looked_up = or_(trace.parent_span_id.is_(None), ~stored_parent)
    return func.coalesce(trace.is_root, looked_up)


def span_scope(trace, org_uuid, project_id: Optional[str]) -> list:
    clauses = [trace.organization_id == org_uuid, trace.deleted_at.is_(None)]
    if project_id:
        clauses.append(trace.project_id == project_id)
    return clauses


def _trace_has(org_uuid, project_id, condition: Callable[[Any], Any], *, few=False) -> Any:
    """Keep spans of traces where some row matches *condition*.

    ``few``: the condition picks out a handful of traces (one test run, say). ANY(ARRAY())
    runs it once and looks their spans up by trace_id; a plain IN let the planner scan
    the whole project instead (21 ms vs 0.8 ms on dev data, and growing with the project).
    """
    other = aliased(models.Trace)
    trace_ids = select(other.trace_id).where(
        *span_scope(other, org_uuid, project_id), condition(other)
    )
    if few:
        return models.Trace.trace_id == any_(func.array(trace_ids.scalar_subquery()))
    return models.Trace.trace_id.in_(trace_ids)


def run_trace_clause(org_uuid, project_id, test_run_id) -> Any:
    """Keep every span of the traces a test run owns, not just the root rows it is stamped on."""
    return _trace_has(org_uuid, project_id, lambda t: t.test_run_id == test_run_id, few=True)


def _trace_lacks(org_uuid, project_id, condition: Callable[[Any], Any]) -> Any:
    """Keep spans of traces where no row matches *condition*."""
    other = aliased(models.Trace)
    return ~exists().where(
        other.trace_id == models.Trace.trace_id,
        *span_scope(other, org_uuid, project_id),
        condition(other),
    )


def _row_clauses(filters: SpanFilters, skip: Collection[str]) -> list:
    trace = models.Trace
    clauses = []
    if filters.span_types and SKIP_SPAN_TYPE not in skip:
        clauses.append(trace.span_type.in_(filters.span_types))
    if filters.span_names and SKIP_SPAN_NAME not in skip:
        clauses.append(trace.span_name.in_(filters.span_names))
    if filters.search and filters.search.strip():
        term = filters.search.strip()
        clauses.append(
            or_(
                trace.span_name.icontains(term, autoescape=True),
                trace.span_id.icontains(term, autoescape=True),
                trace.trace_id.icontains(term, autoescape=True),
            )
        )
    if filters.is_root is not None:
        is_root = span_is_root_expr(trace)
        clauses.append(is_root if filters.is_root else ~is_root)
    if filters.status_code:
        clauses.append(trace.status_code == filters.status_code)
    if filters.environment:
        clauses.append(trace.environment == filters.environment)
    return clauses + _range_clauses(filters)


def _range_clauses(filters: SpanFilters) -> list:
    trace = models.Trace
    bounds = [
        (filters.start_time_after, trace.start_time.__ge__),
        (filters.start_time_before, trace.start_time.__le__),
        (filters.duration_min_ms, trace.duration_ms.__ge__),
        (filters.duration_max_ms, trace.duration_ms.__le__),
    ]
    return [compare(value) for value, compare in bounds if value is not None]


def _trace_clauses(org_uuid, project_id, filters: SpanFilters) -> list:
    test_ids = [
        (filters.test_run_id, lambda t: t.test_run_id == filters.test_run_id),
        (filters.test_result_id, lambda t: t.test_result_id == filters.test_result_id),
        (filters.test_id, lambda t: t.test_id == filters.test_id),
    ]
    clauses = [
        _trace_has(org_uuid, project_id, condition, few=True)
        for value, condition in test_ids
        if value
    ]

    wanted = []
    if filters.trace_source != TraceSource.ALL:
        wanted.append(
            (filters.trace_source == TraceSource.TEST, lambda t: t.test_run_id.isnot(None))
        )
    if filters.trace_type != TraceType.ALL:
        wanted.append(
            (filters.trace_type == TraceType.MULTI_TURN, lambda t: t.conversation_id.isnot(None))
        )
    return clauses + [
        (_trace_has if present else _trace_lacks)(org_uuid, project_id, condition)
        for present, condition in wanted
    ]


def provider_clause(recorded: Collection[str], model_names: Collection[str]) -> Any:
    """Match spans served by providers already resolved to (recorded, model) sets.

    Mirrors ``resolve_provider``: a recorded provider wins, and only a span that
    recorded none is placed by its model name.
    """
    entry = span_breakdown_entry()
    recorded_col = span_recorded_provider_expr(entry)
    clauses = []
    if recorded:
        clauses.append(recorded_col.in_(list(recorded)))
    if model_names:
        clauses.append(and_(recorded_col.is_(None), span_model_expr(entry).in_(list(model_names))))
    return or_(*clauses) if clauses else false()


def span_agent_expr() -> Any:
    """The agent a span ran, for agent spans (``ai.agent.name``)."""
    return models.Trace.attributes[AISpanAttributes.AGENT_NAME].astext


def span_tool_expr() -> Any:
    """The tool a span called, for tool spans (``ai.tool.name``)."""
    return models.Trace.attributes[AISpanAttributes.TOOL_NAME].astext


def span_filter_clauses(
    org_uuid,
    project_id: Optional[str],
    filters: SpanFilters,
    *,
    skip: Collection[str] = frozenset(),
) -> List[Any]:
    """Every WHERE clause for *filters* except provider, which needs a lookup first.

    ``skip`` leaves a filter out, which is how a facet ignores its own selection.
    """
    clauses = span_scope(models.Trace, org_uuid, project_id)
    clauses += _row_clauses(filters, skip)
    clauses += _trace_clauses(org_uuid, project_id, filters)
    if filters.models and SKIP_MODEL not in skip:
        clauses.append(span_model_expr(span_breakdown_entry()).in_(filters.models))
    if filters.agents and SKIP_AGENT not in skip:
        clauses.append(span_agent_expr().in_(filters.agents))
    if filters.tools:
        clauses.append(span_tool_expr().in_(filters.tools))
    if filters.target is not None:
        # Imports the SDK, which a core install hasn't: only when a target is given.
        from rhesis.backend.app.crud.span_target_sql import target_clause

        clauses.append(target_clause(filters.target))
    return clauses


def span_sort_clauses(sort_by: Optional[str], sort_order: str) -> list:
    """ORDER BY for the spans list, always ending start_time then id so pages don't overlap."""
    if sort_by and sort_by not in SPAN_SORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot sort spans by '{sort_by}'. "
                f"Sortable fields: {', '.join(sorted(SPAN_SORT_FIELDS))}"
            ),
        )

    clauses = []
    if sort_by:
        expression = {
            "start_time": models.Trace.start_time,
            "duration_ms": models.Trace.duration_ms,
            "span_name": models.Trace.span_name,
            "total_tokens": span_token_columns()[2],
            "cost_usd": span_cost_expr(span_breakdown_entry()),
        }[sort_by]
        ordered = asc(expression) if sort_order.lower() == "asc" else desc(expression)
        clauses.append(ordered.nullslast())
    if sort_by != "start_time":
        clauses.append(desc(models.Trace.start_time))
    clauses.append(desc(models.Trace.id))
    return clauses
