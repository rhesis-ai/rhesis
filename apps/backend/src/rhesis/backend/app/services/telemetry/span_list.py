"""The spans list and its facets: one row per span, for the traces page's Spans view."""

from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.constants import AISpanAttributes
from rhesis.backend.app.crud.telemetry import (
    TraceContext,
    query_spans,
    span_facets,
    trace_context_for,
)
from rhesis.backend.app.schemas.telemetry import (
    SpanFacetsResponse,
    SpanFacetValue,
    SpanFilters,
    SpanListResponse,
    SpanSummary,
)
from rhesis.backend.app.services.telemetry.providers import resolve_provider

_NO_CONTEXT = TraceContext(None, None, None, None, None)


def _int_or_none(value) -> Optional[int]:
    return None if value is None else int(value)


def _str_or_none(value) -> Optional[str]:
    return None if value is None else str(value)


def _summary(row, context: TraceContext) -> SpanSummary:
    provider = None
    if row.model:
        provider = resolve_provider(
            {AISpanAttributes.MODEL_PROVIDER: row.recorded_provider}, row.model
        )
    return SpanSummary(
        id=str(row.id),
        span_id=row.span_id,
        trace_id=row.trace_id,
        parent_span_id=row.parent_span_id,
        is_root=row.parent_span_id is None,
        project_id=str(row.project_id),
        span_name=row.span_name,
        span_type=row.span_type,
        trace_name=context.trace_name,
        start_time=row.start_time,
        duration_ms=row.duration_ms or 0.0,
        status_code=row.status_code,
        environment=row.environment,
        conversation_id=row.conversation_id or context.conversation_id,
        test_run_id=_str_or_none(context.test_run_id),
        test_result_id=_str_or_none(context.test_result_id),
        test_id=_str_or_none(context.test_id),
        model=row.model,
        provider=provider,
        input_tokens=_int_or_none(row.input_tokens),
        output_tokens=_int_or_none(row.output_tokens),
        total_tokens=_int_or_none(row.total_tokens),
        cost_usd=row.cost_usd,
    )


def list_spans(
    db: Session,
    organization_id: str,
    project_id: Optional[str],
    filters: SpanFilters,
    sort_by: Optional[str],
    sort_order: str,
    limit: int,
    offset: int,
) -> SpanListResponse:
    rows, total = query_spans(
        db,
        organization_id,
        project_id,
        filters,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
    contexts = trace_context_for(
        db, organization_id, project_id, sorted({row.trace_id for row in rows})
    )
    return SpanListResponse(
        spans=[_summary(row, contexts.get(row.trace_id, _NO_CONTEXT)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_span_facets(
    db: Session,
    organization_id: str,
    project_id: Optional[str],
    filters: SpanFilters,
    name_limit: int,
) -> SpanFacetsResponse:
    facets = span_facets(db, organization_id, project_id, filters, name_limit=name_limit)

    def values(rows) -> list:
        return [SpanFacetValue(value=row.value, count=row.count) for row in rows]

    return SpanFacetsResponse(
        span_types=values(facets.span_types),
        span_names=values(facets.span_names),
        span_names_truncated=facets.span_names_truncated,
        models=values(facets.models),
    )
