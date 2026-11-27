"""Telemetry router for trace ingestion and queries."""

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Iterator, List, Optional, TypeVar
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from rhesis.backend.app import schemas
from rhesis.backend.app.auth.quota_gates import require_backstop
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import (
    AISpanAttributes,
    EnrichedDataKeys,
    EntityType,
    SpanType,
    TestResultStatus,
)
from rhesis.backend.app.crud import file as file_crud
from rhesis.backend.app.crud.telemetry import (
    get_trace_by_db_id,
    get_trace_by_id,
    get_trace_metrics_aggregated,
    list_trace_agents,
    list_trace_providers,
    query_traces,
    validate_uuid_param,
)
from rhesis.backend.app.database import temporary_project_scope
from rhesis.backend.app.dependencies import (
    assert_project_access,
    get_project_context,
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.routers import telemetry_intake as intake
from rhesis.backend.app.routers.base import RhesisRouter, run_first
from rhesis.backend.app.schemas.metric import read_target
from rhesis.backend.app.schemas.telemetry import (
    OTELTraceBatch,
    SpanAttributeCatalogue,
    SpanFacetsResponse,
    SpanFilters,
    SpanListResponse,
    StatusCode,
    TraceDetailResponse,
    TraceIngestResponse,
    TraceListResponse,
    TraceMetricsResponse,
    TraceSource,
    TraceSummary,
    TraceType,
)
from rhesis.backend.app.services.project_membership import list_other_member_projects
from rhesis.backend.app.services.telemetry.admission import InflightSlot, IngestRejected
from rhesis.backend.app.services.telemetry.ingest import (
    TooManySpans,
    apply_span_limits,
)
from rhesis.backend.app.services.telemetry.span_attributes import get_attribute_catalogue
from rhesis.backend.app.services.telemetry.span_list import get_span_facets, list_spans
from rhesis.backend.app.services.telemetry.token_totals import (
    trace_cost_usd,
    trace_summary_usage,
    trace_token_totals,
)
from rhesis.backend.app.utils.rate_limit import limiter

# Legacy alias for backward compatibility
TraceResponse = TraceIngestResponse

router = RhesisRouter(
    prefix="/telemetry",
    tags=["telemetry"],
    responses={404: {"description": "Not found"}},
    resource="telemetry",
)
logger = logging.getLogger(__name__)

T = TypeVar("T")


def _parse_sdk_batch(body: bytes) -> OTELTraceBatch:
    try:
        return OTELTraceBatch.model_validate_json(body)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_url=False, include_context=False))


# SDK span export; metered by the tracing quota instead of the default limit.
@router.post("/traces", response_model=TraceResponse)
@limiter.exempt
@run_first(intake.ingest_slot)
async def ingest_trace(
    request: Request,
    slot: InflightSlot = Depends(intake.ingest_slot),
    tenant_context=Depends(get_tenant_context),
    scope_project_id: str | None = Depends(get_project_context),
    current_user: User = Depends(require_current_user_or_token),
    _backstop: None = Depends(require_backstop(QuotaResource.TRACING_SPANS)),
) -> TraceResponse:
    """
    Accept a batch of SDK spans (``OTELTraceBatch`` JSON) and queue it for storage.

    The spans are validated and queued, then stored by a worker, so they appear
    in the trace list a moment after this returns. A resent batch is safe: spans
    already stored (same trace and span id) are skipped.

    **Authentication**: Requires valid API key in Bearer token

    **Quota**: Spans are metered (``QuotaResource.TRACING_SPANS``) and
    subject to a backstop at 10x the tier limit. The published limit is
    enforced by notification and retention, not by rejection; the backstop
    only fires for runaway or abusive exporters. Fails open on lookup
    errors so a billing-side problem never breaks ingestion.

    **Limits**: see ``TraceIngestSettings``. Over a rate or capacity limit the
    response is 429 or 503 with ``Retry-After``; the SDK exporter retries both.

    Raises:
        401: Invalid or missing API key
        403: Project access denied
        413: Body or span count over the limit
        422: Invalid trace format
        429: Organization over its ingest rate
        503: Ingest busy or unavailable
    """
    organization_id = tenant_context[0]
    limits = intake.settings()
    try:
        body = await intake.admitted_body(organization_id, request, limits, slot)
        trace_batch = await intake.in_thread(_parse_sdk_batch, body)
        await intake.in_thread(apply_span_limits, trace_batch.spans, limits)
        jobs = await intake.in_thread(
            intake.ingest_jobs,
            request,
            current_user,
            tenant_context,
            trace_batch.spans,
            scope_project_id,
        )
        for job in jobs:
            await intake.enqueue(job, limits)
    except intake.ProjectUnresolved:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No project_id could be resolved. Use a project-scoped token, "
                "set RHESIS_PROJECT_ID, or pass X-Project-Id header."
            ),
        )
    except IngestRejected as exc:
        raise intake.as_http_exception(exc.rejection)
    except TooManySpans as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))

    trace_id = trace_batch.spans[0].trace_id
    logger.info(
        f"📊 TRACE INGESTION | trace_id={trace_id} | spans={len(trace_batch.spans)} | "
        f"projects={','.join(job.project_id for job in jobs)} | org={organization_id} | queued"
    )
    return TraceResponse(status="received", span_count=len(trace_batch.spans), trace_id=trace_id)


@router.get("/traces", response_model=TraceListResponse)
def list_traces(
    request: Request,
    current_user: User = Depends(require_current_user_or_token),
    project_id: Optional[str] = Query(
        None,
        description=(
            "Project ID filter. Defaults to the session project from X-Project-Id "
            "(or the API token's project scope). When omitted and no session project "
            "is set, only org-level traces (project_id = NULL) are returned "
            "(fail-closed). Must be a project the caller is a member of."
        ),
    ),
    endpoint_id: Optional[str] = Query(None, description="Endpoint ID filter"),
    environment: Optional[str] = Query(None, description="Environment filter"),
    search: Optional[str] = Query(
        None,
        description=(
            "Case-insensitive search across trace ID, operation names, endpoint metadata, "
            "and conversation text"
        ),
    ),
    span_name: Optional[str] = Query(
        None,
        description="Exact span name filter (e.g., 'ai.llm.invoke'); prefer `search` for UI",
    ),
    status_code: Optional[str] = Query(None, description="Status code filter (OK, ERROR)"),
    start_time_after: Optional[datetime] = Query(None, description="Start time >= (ISO 8601)"),
    start_time_before: Optional[datetime] = Query(None, description="Start time <= (ISO 8601)"),
    duration_min_ms: Optional[float] = Query(None, description="Minimum duration in milliseconds"),
    duration_max_ms: Optional[float] = Query(None, description="Maximum duration in milliseconds"),
    test_run_id: Optional[str] = Query(None, description="Filter by test run ID"),
    test_result_id: Optional[str] = Query(None, description="Filter by test result ID"),
    test_id: Optional[str] = Query(None, description="Filter by test ID"),
    conversation_id: Optional[str] = Query(None, description="Filter by conversation ID"),
    provider: Optional[List[str]] = Query(
        None,
        description=(
            "Filter by LLM provider, repeatable. A trace matches when any of its priced "
            "calls was served by one of the named providers. Values come from "
            "GET /telemetry/providers; a trace enrichment has not priced yet matches none."
        ),
    ),
    agent: Optional[List[str]] = Query(
        None,
        description=(
            "Filter by agent name (`ai.agent.name`), repeatable. A trace matches when any of "
            "its spans ran one of the named agents. Values come from GET /telemetry/agents."
        ),
    ),
    trace_source: TraceSource = Query(
        TraceSource.ALL,
        description=(
            "Filter by trace source: 'all' (default), 'test' (test execution traces), "
            "or 'operation' (normal app traces)"
        ),
    ),
    trace_type: TraceType = Query(
        TraceType.ALL,
        description=(
            "Filter: 'all' (default), 'Single-Turn' (no conversation_id), "
            "'Multi-Turn' (has conversation_id)"
        ),
    ),
    trace_metrics_status: Optional[TestResultStatus] = Query(
        None,
        description="Filter by trace metrics evaluation status (Pass, Fail, Error)",
    ),
    root_spans_only: bool = Query(
        True,
        description=("Return only root spans (one per trace). Set to false to return all spans."),
    ),
    sort_by: Optional[str] = Query(
        None,
        description=(
            "Field to sort by. One of: "
            "start_time, duration_ms, trace_id, environment, root_operation, "
            "span_count, total_tokens, total_input_tokens, total_output_tokens, "
            "total_cost_usd, total_input_cost_usd, total_output_cost_usd, model."
        ),
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    limit: int = Query(100, ge=1, le=1000, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    scope_project_id: Optional[str] = Depends(get_project_context),
) -> TraceListResponse:
    """
    List traces with filters and pagination.

    **Authentication**: Requires valid API key

    **Trace Source Filter**:
    - `all` (default): Returns all traces
    - `test`: Returns only test execution traces (with test_run_id)
    - `operation`: Returns only normal application traces (without test_run_id)

    **Root Spans vs All Spans**:
    - By default (root_spans_only=true), returns one entry per trace (root span only)
    - Set root_spans_only=false to return all spans (useful for detailed analysis)

    **Filters**:
    - `project_id`: Filter by project. Defaults to the session project from
      `X-Project-Id` (or the API token's project scope). When omitted with no
      session project, only org-level traces are returned (fail-closed).
    - `environment`: Filter by environment (development, staging, production)
    - `search`: Substring search across trace ID, operations, endpoint name/URL, conversation I/O
    - `span_name`: Exact match on root span name (legacy; prefer `search`)
    - `status_code`: Filter by span status (OK, ERROR)
    - `trace_metrics_status`: Filter by evaluation status (Pass, Fail, Error)
    - `start_time_after`: Filter by start time >= timestamp
    - `start_time_before`: Filter by start time <= timestamp
    - `duration_min_ms` / `duration_max_ms`: Filter by duration range
    - `test_run_id`: Filter by test run ID (for test execution traces)
    - `test_result_id`: Filter by test result ID (for test execution traces)
    - `test_id`: Filter by test ID (for test execution traces)
    - `conversation_id`: Filter by conversation ID (for multi-turn traces)

    **Pagination**:
    - `limit`: Number of results per page (default: 100, max: 1000)
    - `offset`: Number of results to skip (default: 0)

    Returns:
        Paginated list of trace summaries
    """
    organization_id, user_id = tenant_context
    effective_project_id = project_id or scope_project_id

    if project_id is not None:
        assert_project_access(request, current_user, project_id, db=db)

    try:
        query_kwargs = dict(
            db=db,
            organization_id=organization_id,
            project_id=effective_project_id,
            endpoint_id=endpoint_id,
            root_spans_only=root_spans_only,
            trace_source=trace_source,
            trace_type=trace_type,
            environment=environment,
            search=search,
            span_name=span_name,
            status_code=status_code,
            start_time_after=start_time_after,
            start_time_before=start_time_before,
            duration_min_ms=duration_min_ms,
            duration_max_ms=duration_max_ms,
            test_run_id=test_run_id,
            test_result_id=test_result_id,
            test_id=test_id,
            conversation_id=conversation_id,
            providers=provider,
            agents=agent,
            trace_metrics_status=(trace_metrics_status.value if trace_metrics_status else None),
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        # When the query param project differs from the X-Project-Id session scope,
        # rebind ORM auto-filter for this query so project-scoped rows are visible.
        if effective_project_id and effective_project_id != scope_project_id:
            with temporary_project_scope(db, organization_id, user_id, effective_project_id):
                rows = query_traces(**query_kwargs)
        else:
            rows = query_traces(**query_kwargs)

        total = rows[0].total if rows else 0

        summaries = []
        for row in rows:
            trace = row.trace
            has_errors = trace.status_code == StatusCode.ERROR.value
            usage = trace_summary_usage(trace.enriched_data, row.llm_tokens)

            # Get endpoint information from eagerly loaded relationships
            trace_endpoint_id = None
            trace_endpoint_name = None
            if (
                trace.test_result
                and trace.test_result.test_configuration
                and trace.test_result.test_configuration.endpoint
            ):
                endpoint = trace.test_result.test_configuration.endpoint
                trace_endpoint_id = str(endpoint.id)
                trace_endpoint_name = endpoint.name

            # Outcome and annotations come from the first root: a conversation lists
            # its latest turn, but its verdict and human annotations live on the first.
            first_root = row.first_root
            trace_metrics_status_name = None
            if first_root.trace_metrics_status:
                trace_metrics_status_name = first_root.trace_metrics_status.name

            has_annotations = bool(first_root.annotations)

            conversation_input = None
            if isinstance(trace.attributes, dict):
                raw_input = trace.attributes.get("rhesis.conversation.input")
                if raw_input is not None:
                    conversation_input = str(raw_input)

            agent_name = (trace.attributes or {}).get(AISpanAttributes.AGENT_NAME)

            summary = TraceSummary(
                trace_id=trace.trace_id,
                project_id=str(trace.project_id),
                environment=trace.environment,
                conversation_id=trace.conversation_id,
                conversation_input=conversation_input,
                start_time=trace.start_time,
                duration_ms=trace.duration_ms or 0.0,
                span_count=row.span_count,
                root_operation=trace.span_name,
                agent_name=str(agent_name) if agent_name else None,
                status_code=trace.status_code,
                test_run_id=str(trace.test_run_id) if trace.test_run_id else None,
                test_result_id=str(trace.test_result_id) if trace.test_result_id else None,
                test_id=str(trace.test_id) if trace.test_id else None,
                endpoint_id=trace_endpoint_id,
                endpoint_name=trace_endpoint_name,
                **usage,
                has_errors=has_errors,
                trace_metrics_status=trace_metrics_status_name,
                execution=first_root.execution,
                verdict=first_root.verdict,
                has_annotations=has_annotations,
                last_annotation=first_root.last_annotation,
                matches_annotation=first_root.matches_annotation,
                tags_count=row.tags_count,
                comments_count=row.comments_count,
            )
            summaries.append(summary)

        logger.info(
            f"Listed {len(rows)} traces for project {project_id} (total: {total}, offset: {offset})"
        )

        return TraceListResponse(
            traces=summaries,
            total=total,
            limit=limit,
            offset=offset,
        )

    except HTTPException:
        # A deliberate 4xx, such as an unsortable sort_by, must not become a 500.
        raise
    except Exception as e:
        # Check if it's a database permission error
        error_msg = str(e).lower()
        if "permission denied" in error_msg or "insufficient privilege" in error_msg:
            logger.error(
                f"Database permission error while listing traces for org {organization_id}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Database access denied. Please contact support to resolve permission issues."
                ),
            )

        # Log and return error for other database issues
        logger.error(
            f"Failed to list traces for org {organization_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve traces. Check server logs for details.",
        )


def span_filter_params(
    span_type: Optional[List[str]] = Query(
        None, description="Span type, repeatable (llm.invoke, tool.invoke, span, ...)"
    ),
    span_name: Optional[List[str]] = Query(None, description="Exact span name, repeatable"),
    search: Optional[str] = Query(
        None, description="Case-insensitive substring of span name, span ID or trace ID"
    ),
    is_root: Optional[bool] = Query(None, description="true: root spans only; false: children"),
    status_code: Optional[str] = Query(None, description="Status code filter (OK, ERROR)"),
    environment: Optional[str] = Query(None, description="Environment filter"),
    start_time_after: Optional[datetime] = Query(None, description="Start time >= (ISO 8601)"),
    start_time_before: Optional[datetime] = Query(None, description="Start time <= (ISO 8601)"),
    duration_min_ms: Optional[float] = Query(None, description="Minimum duration in milliseconds"),
    duration_max_ms: Optional[float] = Query(None, description="Maximum duration in milliseconds"),
    test_run_id: Optional[str] = Query(
        None, description="Spans of traces from this test run (children included)"
    ),
    test_result_id: Optional[str] = Query(
        None, description="Spans of traces from this test result (children included)"
    ),
    test_id: Optional[str] = Query(
        None, description="Spans of traces from this test (children included)"
    ),
    trace_type: TraceType = Query(
        TraceType.ALL,
        description="'Multi-Turn': spans of traces with a conversation; 'Single-Turn': without",
    ),
    trace_source: TraceSource = Query(
        TraceSource.ALL, description="'test' or 'operation' traces; 'all' by default"
    ),
    model: Optional[List[str]] = Query(None, description="Model name, repeatable"),
    provider: Optional[List[str]] = Query(
        None, description="LLM provider, repeatable; values from GET /telemetry/providers"
    ),
    agent: Optional[List[str]] = Query(
        None, description="Agent name (`ai.agent.name`), repeatable; matches the agent's spans"
    ),
    tool: Optional[List[str]] = Query(
        None, description="Tool name (`ai.tool.name`), repeatable; matches the tool's calls"
    ),
    target: Optional[str] = Query(
        None,
        description=(
            "A metric target as JSON, as stored in a metric's config.target: only the spans "
            "it picks, the root span of each unit. Applies with the other filters."
        ),
    ),
) -> SpanFilters:
    """Filters shared by the spans list and its facets."""
    for value, name in (
        (test_run_id, "test_run_id"),
        (test_result_id, "test_result_id"),
        (test_id, "test_id"),
    ):
        validate_uuid_param(value, name)
    return SpanFilters(
        span_types=span_type,
        span_names=span_name,
        search=search,
        is_root=is_root,
        status_code=status_code,
        environment=environment,
        start_time_after=start_time_after,
        start_time_before=start_time_before,
        duration_min_ms=duration_min_ms,
        duration_max_ms=duration_max_ms,
        test_run_id=test_run_id,
        test_result_id=test_result_id,
        test_id=test_id,
        trace_type=trace_type,
        trace_source=trace_source,
        models=model,
        providers=provider,
        agents=agent,
        tools=tool,
        target=_parse_target(target),
    )


def _parse_target(raw: Optional[str]) -> Any:
    """The ``target`` query parameter as the SDK's Target; 422 naming what is wrong."""
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid target: not JSON ({e})",
        ) from e
    try:
        return read_target(value)
    except ImportError as e:  # a core install, which runs no metric
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Targets need the metrics SDK"
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@contextmanager
def _requested_project(
    request: Request,
    current_user: User,
    db: Session,
    tenant_context,
    project_id: Optional[str],
    scope_project_id: Optional[str],
) -> Iterator[Optional[str]]:
    """Scope *db* to the project a read asks for, like ``list_traces``; yields its id.

    A ``project_id`` is access-checked. One other than the session's is read under a
    temporary rebind so the ORM filter and RLS let its rows through.
    """
    organization_id, user_id = tenant_context
    if project_id is not None:
        project_id = assert_project_access(request, current_user, project_id, db=db)
    effective_project_id = project_id or scope_project_id
    if effective_project_id and effective_project_id != scope_project_id:
        with temporary_project_scope(db, organization_id, user_id, effective_project_id):
            yield effective_project_id
    else:
        yield effective_project_id


def _in_requested_project(
    request: Request,
    current_user: User,
    db: Session,
    tenant_context,
    project_id: Optional[str],
    scope_project_id: Optional[str],
    run: Callable[[str, Optional[str]], T],
) -> T:
    """Run *run(organization_id, project_id)* under :func:`_requested_project`."""
    organization_id, _ = tenant_context
    try:
        with _requested_project(
            request, current_user, db, tenant_context, project_id, scope_project_id
        ) as effective_project_id:
            return run(organization_id, effective_project_id)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e).lower()
        if "permission denied" in error_msg or "insufficient privilege" in error_msg:
            logger.error(f"Database permission error reading spans: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Database access denied. Please contact support to resolve permission issues."
                ),
            )
        logger.error(f"Failed to read spans for org {organization_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve spans. Check server logs for details.",
        )


@router.get("/spans", response_model=SpanListResponse)
def list_spans_endpoint(
    request: Request,
    current_user: User = Depends(require_current_user_or_token),
    project_id: Optional[str] = Query(
        None,
        description=(
            "Project ID filter. Defaults to the session project from X-Project-Id. "
            "Must be a project the caller is a member of."
        ),
    ),
    filters: SpanFilters = Depends(span_filter_params),
    sort_by: Optional[str] = Query(
        None,
        description=(
            "Field to sort by. One of: start_time, duration_ms, span_name, total_tokens, "
            "cost_usd. Nulls sort last either way."
        ),
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    limit: int = Query(100, ge=1, le=1000, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    scope_project_id: Optional[str] = Depends(get_project_context),
) -> SpanListResponse:
    """List spans, one row per span, with filters, sorting and pagination.

    Test ids, ``trace_source`` and ``trace_type`` describe the trace: they match every
    span of a matching trace, not only its root. ``cost_usd`` is set only for LLM calls
    enrichment has priced.

    ``target`` is a metric target as JSON (URL-encoded), and keeps exactly the spans it
    picks, matched as a metric's evaluation matches them: for a span target or a preset,
    each matching span; for ``turn``, each turn's root span; for ``run``, each trace's first
    root; for ``conversation``, the first root of each conversation. It applies together
    with every other filter, ``tool`` and ``model`` included. A target that isn't JSON or
    isn't valid is a 422 naming the problem.
    """
    return _in_requested_project(
        request,
        current_user,
        db,
        tenant_context,
        project_id,
        scope_project_id,
        lambda organization_id, effective_project_id: list_spans(
            db,
            organization_id,
            effective_project_id,
            filters,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        ),
    )


@router.get("/spans/facets", response_model=SpanFacetsResponse)
def get_span_facets_endpoint(
    request: Request,
    current_user: User = Depends(require_current_user_or_token),
    project_id: Optional[str] = Query(
        None, description="Project ID. Defaults to the session project from X-Project-Id."
    ),
    filters: SpanFilters = Depends(span_filter_params),
    name_limit: int = Query(100, ge=1, le=500, description="Most span names to return"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    scope_project_id: Optional[str] = Depends(get_project_context),
) -> SpanFacetsResponse:
    """Span types, span names and models with counts, for the span filters.

    Takes the same filters as ``GET /telemetry/spans``. Each facet ignores its own
    filter, so with one type selected the type facet still lists the others.
    """
    return _in_requested_project(
        request,
        current_user,
        db,
        tenant_context,
        project_id,
        scope_project_id,
        lambda organization_id, effective_project_id: get_span_facets(
            db, organization_id, effective_project_id, filters, name_limit=name_limit
        ),
    )


@router.get("/attributes", response_model=SpanAttributeCatalogue)
def get_attribute_catalogue_endpoint(
    request: Request,
    current_user: User = Depends(require_current_user_or_token),
    project_id: Optional[str] = Query(
        None, description="Project ID. Defaults to the session project from X-Project-Id."
    ),
    kind: Optional[str] = Query(
        None,
        max_length=SpanType.MAX_LENGTH,
        description="Span kind (span_type: llm.invoke, tool.invoke, span, ...); all kinds if unset",
    ),
    days: int = Query(7, ge=1, le=90, description="Read spans started in the last N days"),
    limit: int = Query(100, ge=1, le=500, description="Most attribute keys per kind"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    scope_project_id: Optional[str] = Depends(get_project_context),
) -> SpanAttributeCatalogue:
    """Attribute keys each span kind carries, with coverage, type and top values.

    Reads the most recent spans of each kind only (at most 2000 per kind), so it stays
    cheap on large projects. Keys where nearly every span has its own value (ids) are marked
    ``unique``; they make poor suggestions.
    """
    return _in_requested_project(
        request,
        current_user,
        db,
        tenant_context,
        project_id,
        scope_project_id,
        lambda organization_id, effective_project_id: get_attribute_catalogue(
            db, organization_id, effective_project_id, kind=kind, days=days, limit=limit
        ),
    )


@router.get("/spans/{span_db_id}/lookup")
def lookup_span(
    span_db_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    scope_project_id: Optional[str] = Depends(get_project_context),
):
    """
    Resolve a span's database UUID to its trace_id and project_id.

    Used for navigation from tasks/comments linked to a Trace entity. The
    span's ``trace`` row carries a FORCE-enabled ``project_isolation`` RLS
    policy, so a lookup scoped to the caller's active project silently misses
    a span whose trace lives in a different (but accessible) project — probe
    the caller's other projects before giving up. See ``routers/resolve.py``
    for the full rationale.
    """
    organization_id, user_id = tenant_context
    span = get_trace_by_db_id(db, str(span_db_id), organization_id)

    if not span:
        for candidate_project_id, _ in list_other_member_projects(
            db, organization_id, user_id, scope_project_id
        ):
            with temporary_project_scope(db, organization_id, user_id, candidate_project_id):
                span = get_trace_by_db_id(db, str(span_db_id), organization_id)
            if span:
                break

    if not span:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Span {span_db_id} not found",
        )
    return {
        "trace_id": span.trace_id,
        "project_id": str(span.project_id),
        "span_id": span.span_id,
    }


@router.get("/traces/{trace_id}", response_model=TraceDetailResponse)
def get_trace(
    request: Request,
    trace_id: str,
    project_id: str = Query(..., description="Project ID"),
    current_user: User = Depends(require_current_user_or_token),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    scope_project_id: Optional[str] = Depends(get_project_context),
) -> TraceDetailResponse:
    """
    Get detailed trace with all spans.

    Returns the complete trace including:
    - All spans in the trace
    - Parent-child relationships
    - Enriched data (costs, anomalies, metadata)

    Args:
        trace_id: OpenTelemetry trace ID (32-char hex)
        project_id: The trace's project; read even when the session's project is another

    Returns:
        Complete trace details with all spans

    Raises:
        403: No access to the project
        404: Trace not found
    """
    # The response reads relationships too, so all of it runs in the project's scope.
    with _requested_project(
        request, current_user, db, tenant_context, project_id, scope_project_id
    ) as effective_project_id:
        return _trace_detail(db, tenant_context[0], trace_id, effective_project_id)


def _trace_detail(
    db: Session, organization_id: str, trace_id: str, project_id: str
) -> TraceDetailResponse:
    try:
        # Fetch all spans for trace with eager loading of relationships, including
        # the nested test_result.test_configuration.endpoint chain in the same query
        spans = get_trace_by_id(
            db=db,
            trace_id=trace_id,
            project_id=project_id,
            organization_id=organization_id,
            eager_load=[
                "project",
                "test_run",
                "test_result",
                "test",
                "test_result.test_configuration.endpoint",
                "trace_metrics_status",
                "annotations",
            ],
        )

        if not spans:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Trace {trace_id} not found"
            )

        # Build proper span tree
        from rhesis.backend.app.services.telemetry.tree_builder import build_span_tree

        # enriched_data is trace-level and written onto every span, so any span
        # carries the whole breakdown. Index it once for the tree builder.
        costs = (spans[0].enriched_data or {}).get(EnrichedDataKeys.COSTS) or {}
        cost_by_span_id = {
            entry[EnrichedDataKeys.SPAN_ID]: entry
            for entry in costs.get(EnrichedDataKeys.BREAKDOWN) or []
            if entry.get(EnrichedDataKeys.SPAN_ID)
        }

        root_spans = build_span_tree(spans, cost_by_span_id)

        # Calculate trace-level metrics
        total_duration = max(span.end_time for span in spans) - min(
            span.start_time for span in spans
        )
        total_input_tokens, total_output_tokens, total_tokens = trace_token_totals(spans)
        error_count = sum(1 for span in spans if span.status_code == StatusCode.ERROR.value)

        total_cost = trace_cost_usd(spans[0].enriched_data)

        # Build relationship objects from first span
        from rhesis.backend.app.schemas.endpoint import Endpoint
        from rhesis.backend.app.schemas.project import Project
        from rhesis.backend.app.schemas.test import Test
        from rhesis.backend.app.schemas.test_result import TestResult
        from rhesis.backend.app.schemas.test_run import TestRun

        first_span = spans[0]

        # Project (always present)
        project_obj = None
        if first_span.project:
            project_obj = Project.model_validate(first_span.project)

        # Endpoint (if available via test_result.test_configuration.endpoint)
        endpoint_obj = None
        if (
            first_span.test_result
            and hasattr(first_span.test_result, "test_configuration")
            and first_span.test_result.test_configuration
            and hasattr(first_span.test_result.test_configuration, "endpoint")
            and first_span.test_result.test_configuration.endpoint
        ):
            endpoint_obj = Endpoint.model_validate(
                first_span.test_result.test_configuration.endpoint
            )

        # Test run (if from test execution)
        test_run_obj = None
        if first_span.test_run:
            test_run_obj = TestRun.model_validate(first_span.test_run)

        # Test result (if from test execution)
        test_result_obj = None
        if first_span.test_result:
            test_result_obj = TestResult.model_validate(first_span.test_result)

        # Test (if from test execution)
        test_obj = None
        if first_span.test:
            test_obj = Test.model_validate(first_span.test)

        # Resolve conversation_id: the first span (earliest by start_time)
        # may have conversation_id=NULL when the first turn of a stateful
        # endpoint was stored before the ID was known.  Scan all spans so
        # the detail view matches the list view (which uses the latest span).
        trace_conversation_id = next(
            (s.conversation_id for s in spans if s.conversation_id),
            None,
        )

        logger.info(f"Retrieved trace {trace_id} with {len(spans)} span(s)")

        # Get trace metrics status if available
        trace_metrics_status_name = None
        if hasattr(first_span, "trace_metrics_status") and first_span.trace_metrics_status:
            trace_metrics_status_name = first_span.trace_metrics_status.name

        return TraceDetailResponse(
            trace_id=first_span.trace_id,
            project_id=str(first_span.project_id),
            environment=first_span.environment,
            conversation_id=trace_conversation_id,
            start_time=min(span.start_time for span in spans),
            end_time=max(span.end_time for span in spans),
            duration_ms=total_duration.total_seconds() * 1000,
            span_count=len(spans),
            error_count=error_count,
            total_tokens=total_tokens,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_cost_usd=total_cost,
            root_spans=root_spans,
            trace_metrics_status=trace_metrics_status_name,
            execution=first_span.execution,
            verdict=first_span.verdict,
            last_annotation=first_span.last_annotation,
            matches_annotation=first_span.matches_annotation,
            annotation_summary=first_span.annotation_summary,
            project=project_obj,
            endpoint=endpoint_obj,
            test_run=test_run_obj,
            test_result=test_result_obj,
            test=test_obj,
        )

    except HTTPException:
        # Re-raise HTTPExceptions (like 404) as-is
        raise
    except Exception as e:
        # Check if it's a database permission error
        error_msg = str(e).lower()
        if "permission denied" in error_msg or "insufficient privilege" in error_msg:
            logger.error(
                f"Database permission error while retrieving trace {trace_id}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Database access denied. Please contact support to resolve permission issues."
                ),
            )

        # Log and return error for other database issues
        logger.error(
            f"Failed to retrieve trace {trace_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve trace details. Check server logs for details.",
        )


@router.get(
    "/spans/{span_db_id}/files",
    response_model=List[schemas.FileResponse],
)
def list_span_files(
    span_db_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """List files attached to a trace span."""
    organization_id, user_id = tenant_context
    return file_crud.get_files_for_entity(
        db, span_db_id, EntityType.TRACE.value, organization_id, user_id
    )


@router.get("/providers", response_model=List[str])
def get_providers(
    request: Request,
    current_user: User = Depends(require_current_user_or_token),
    project_id: Optional[str] = Query(
        None, description="Project ID. Defaults to the session project from X-Project-Id."
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    scope_project_id: Optional[str] = Depends(get_project_context),
) -> List[str]:
    """LLM providers appearing in this scope's traces, for the traces filter.

    Built from the same data the provider filter matches on, so the list never offers a
    value that would return nothing. A provider neither the trace nor its model name
    identifies comes back as 'unknown', which is a real choice: those traces exist and
    filtering to them is how you find what is not attributed.

    Scoped exactly as ``list_traces`` is, including the access check and the temporary
    rebind: a checklist that answered for a project the caller cannot list would leak
    which models that project runs, and one answering under the wrong scope would come
    back empty beside a table full of rows.
    """
    organization_id, user_id = tenant_context
    if project_id is not None:
        assert_project_access(request, current_user, project_id, db=db)

    effective_project_id = project_id or scope_project_id

    if effective_project_id and effective_project_id != scope_project_id:
        with temporary_project_scope(db, organization_id, user_id, effective_project_id):
            return list_trace_providers(
                db, organization_id=organization_id, project_id=effective_project_id
            )

    return list_trace_providers(
        db, organization_id=organization_id, project_id=effective_project_id
    )


@router.get("/agents", response_model=List[str])
def get_agents(
    request: Request,
    current_user: User = Depends(require_current_user_or_token),
    project_id: Optional[str] = Query(
        None, description="Project ID. Defaults to the session project from X-Project-Id."
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    scope_project_id: Optional[str] = Depends(get_project_context),
) -> List[str]:
    """Agent names (`ai.agent.name`) appearing in this scope's traces, for the traces filter.

    Scoped exactly as ``list_traces`` is.
    """
    return _in_requested_project(
        request,
        current_user,
        db,
        tenant_context,
        project_id,
        scope_project_id,
        lambda organization_id, effective_project_id: list_trace_agents(
            db, organization_id=organization_id, project_id=effective_project_id
        ),
    )


@router.get("/metrics", response_model=TraceMetricsResponse)
def get_metrics(
    request: Request,
    project_id: str = Query(..., description="Project ID"),
    environment: Optional[str] = Query(None, description="Environment filter"),
    start_time_after: Optional[datetime] = Query(None, description="Start time >= (ISO 8601)"),
    start_time_before: Optional[datetime] = Query(None, description="Start time <= (ISO 8601)"),
    test_run_id: Optional[str] = Query(None, description="Scope metrics to a single test run"),
    current_user: User = Depends(require_current_user_or_token),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    scope_project_id: Optional[str] = Depends(get_project_context),
) -> TraceMetricsResponse:
    """
    Get aggregated metrics for traces.

    Returns:
    - Total traces
    - Total spans
    - Token usage (input, output, total)
    - Costs (total USD)
    - Latency statistics (p50, p95, p99)
    - Error rate
    - Operation type breakdown

    **Time Range**: Optional - if not specified, all traces will be included

    Args:
        project_id: Project ID
        environment: Environment filter (optional)
        start_time_after: Start of time range
        start_time_before: End of time range
        test_run_id: Narrow every metric to one test run (optional)

    Returns:
        Aggregated metrics
    """
    organization_id, _ = tenant_context

    with _requested_project(
        request, current_user, db, tenant_context, project_id, scope_project_id
    ) as effective_project_id:
        return _metrics(
            db,
            organization_id,
            effective_project_id,
            environment,
            start_time_after,
            start_time_before,
            test_run_id,
        )


def _metrics(
    db: Session,
    organization_id: str,
    project_id: str,
    environment: Optional[str],
    start_time_after: Optional[datetime],
    start_time_before: Optional[datetime],
    test_run_id: Optional[str],
) -> TraceMetricsResponse:
    try:
        result = get_trace_metrics_aggregated(
            db=db,
            organization_id=organization_id,
            project_id=project_id,
            environment=environment,
            start_time_after=start_time_after,
            start_time_before=start_time_before,
            test_run_id=test_run_id,
        )

        logger.info(f"Calculated metrics for project {project_id}")
        return TraceMetricsResponse(**result)

    except HTTPException:
        # A deliberate 4xx, such as a malformed test_run_id, must not become a 500.
        raise
    except Exception as e:
        # Check if it's a database permission error
        error_msg = str(e).lower()
        if "permission denied" in error_msg or "insufficient privilege" in error_msg:
            logger.error(
                f"Database permission error while calculating metrics "
                f"for project {project_id}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Database access denied. Please contact support to resolve permission issues."
                ),
            )

        # Log and return error for other database issues
        logger.error(
            f"Failed to calculate metrics for project {project_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve trace metrics. Check server logs for details.",
        )
