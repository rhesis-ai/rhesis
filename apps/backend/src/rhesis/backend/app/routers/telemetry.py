"""Telemetry router for trace ingestion and queries."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import EnrichedDataKeys, EntityType, TestResultStatus
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.telemetry import (
    OTELTraceBatch,
    StatusCode,
    TraceDetailResponse,
    TraceIngestResponse,
    TraceListResponse,
    TraceMetricsResponse,
    TraceSource,
    TraceSummary,
    TraceType,
)
from rhesis.backend.app.services.telemetry.enrichment import EnrichmentService
from rhesis.backend.app.services.trace_review_override import (
    apply_review_override as trace_apply_review_override,
)
from rhesis.backend.app.services.trace_review_override import (
    revert_override as trace_revert_override,
)

# Legacy alias for backward compatibility
TraceResponse = TraceIngestResponse

router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"],
    responses={404: {"description": "Not found"}},
)
logger = logging.getLogger(__name__)


@router.post("/traces", response_model=TraceResponse)
def ingest_trace(
    trace_batch: OTELTraceBatch,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
) -> TraceResponse:
    """
    Ingest OpenTelemetry traces from SDK.

    This endpoint receives OTLP-formatted spans and stores them
    for observability and analytics.

    **Authentication**: Requires valid API key in Bearer token

    **Rate Limiting**: Subject to per-project rate limits

    Args:
        trace_batch: Batch of OTEL spans to ingest
        db: Database session
        tenant_context: Authenticated user/API key context

    Returns:
        TraceResponse with ingestion status

    Raises:
        401: Invalid or missing API key
        403: Project access denied
        422: Invalid trace format
        500: Internal server error
    """
    organization_id, user_id = tenant_context

    # Extract metadata
    project_id = trace_batch.spans[0].project_id if trace_batch.spans else None

    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Trace batch must contain at least one span with project_id",
        )

    # Log ingestion (summary only)
    trace_id = trace_batch.spans[0].trace_id
    span_count = len(trace_batch.spans)

    logger.info(
        f"📊 TRACE INGESTION | "
        f"trace_id={trace_id} | "
        f"spans={span_count} | "
        f"project={project_id} | "
        f"org={organization_id}"
    )

    # Pre-storage: inject any parked mapped output into span attributes.
    # Must happen before storage because it mutates span attributes in-place.
    from rhesis.backend.app.services.telemetry.conversation_linking import (
        inject_pending_output,
    )

    try:
        output_injected = inject_pending_output(trace_batch.spans)
        if output_injected > 0:
            logger.info(
                f"Injected mapped output into {output_injected} span(s) for trace_id={trace_id}"
            )
    except Exception as inject_error:
        logger.warning(f"Failed to inject pending output for trace_id={trace_id}: {inject_error}")
        logger.debug("Pending output injection traceback:", exc_info=True)

    # Store spans, then enqueue linking + enrichment as a background task.
    _stage = "span_storage"
    try:
        stored_spans = crud.create_trace_spans(db, trace_batch.spans, organization_id)

        if not stored_spans:
            logger.warning(f"No spans were stored for trace_id={trace_id}")
            return TraceResponse(status="received", span_count=0, trace_id=trace_id)

        unique_trace_ids = list({s.trace_id for s in stored_spans})
        stored_span_ids = [str(s.id) for s in stored_spans]

        logger.info(
            f"Ingested {len(stored_spans)} spans from "
            f"{len(unique_trace_ids)} trace(s) for trace_id={trace_id}"
        )

        # Enqueue post-ingestion work (linking + enrichment) as a background task.
        from rhesis.backend.app.services.telemetry.enrichment import (
            check_workers_available,
        )

        _stage = "worker_check"
        _workers_available = check_workers_available()
        logger.info(
            f"Worker availability for trace_id={trace_id}: {_workers_available}"
        )

        _dispatched_async = False
        if _workers_available:
            from rhesis.backend.tasks.telemetry.post_ingest import post_ingest_link

            first_span = stored_spans[0]
            _stage = "async_dispatch"
            try:
                post_ingest_link.delay(
                    stored_span_ids=stored_span_ids,
                    unique_trace_ids=unique_trace_ids,
                    organization_id=organization_id,
                    project_id=str(project_id),
                    test_run_id=str(first_span.test_run_id) if first_span.test_run_id else None,
                    test_id=str(first_span.test_id) if first_span.test_id else None,
                    test_configuration_id=first_span.attributes.get(
                        "rhesis.test.test_configuration_id"
                    ),
                )
                _dispatched_async = True
                logger.info(f"Dispatched post_ingest_link for trace_id={trace_id}")
            except Exception as broker_err:
                logger.warning(
                    f"Failed to dispatch post_ingest_link for trace_id={trace_id} | "
                    f"error_type={type(broker_err).__name__} | "
                    f"error={broker_err} | "
                    f"falling back to synchronous processing",
                    exc_info=True,
                )

        if not _dispatched_async:
            _stage = "sync_fallback"
            logger.warning(
                f"Running synchronous post-ingestion fallback for trace_id={trace_id} | "
                f"workers_available={_workers_available}"
            )

            # Sync fallback: run linking in-request, enrichment via service
            from rhesis.backend.app.services.telemetry.conversation_linking import (
                apply_pending_conversation_links,
                apply_pending_files,
            )
            from rhesis.backend.app.services.telemetry.linking_service import (
                TraceLinkingService,
            )

            linking_service = TraceLinkingService(db)
            try:
                linking_service.link_traces_for_incoming_batch(
                    spans=stored_spans,
                    organization_id=organization_id,
                )
            except Exception as link_error:
                logger.warning(
                    f"Failed to link traces for trace_id={trace_id}: {link_error}",
                    exc_info=True,
                )

            try:
                apply_pending_conversation_links(db, stored_spans)
            except Exception as conv_error:
                logger.warning(
                    f"Failed to apply conversation links for trace_id={trace_id}: {conv_error}",
                    exc_info=True,
                )

            try:
                apply_pending_files(db, stored_spans)
            except Exception as file_error:
                logger.warning(
                    f"Failed to apply pending files for trace_id={trace_id}: {file_error}",
                    exc_info=True,
                )

            try:
                enrichment_service = EnrichmentService(db)
                enrichment_service.enrich_traces(
                    set(unique_trace_ids),
                    str(project_id),
                    organization_id,
                )
            except Exception as enrich_error:
                logger.warning(
                    f"Failed to enrich traces for trace_id={trace_id}: {enrich_error}",
                    exc_info=True,
                )

        return TraceResponse(
            status="received",
            span_count=len(stored_spans),
            trace_id=trace_id,
        )

    except Exception as e:
        logger.error(
            f"Trace ingestion failed | "
            f"stage={_stage} | "
            f"trace_id={trace_id} | "
            f"org={organization_id} | "
            f"project={project_id} | "
            f"error_type={type(e).__name__} | "
            f"error={e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store trace spans",
        )


@router.get("/traces", response_model=TraceListResponse)
def list_traces(
    project_id: Optional[str] = Query(
        None, description="Project ID (optional - shows all projects if not specified)"
    ),
    endpoint_id: Optional[str] = Query(None, description="Endpoint ID filter"),
    environment: Optional[str] = Query(None, description="Environment filter"),
    span_name: Optional[str] = Query(None, description="Span name filter (e.g., 'ai.llm.invoke')"),
    status_code: Optional[str] = Query(None, description="Status code filter (OK, ERROR)"),
    start_time_after: Optional[datetime] = Query(None, description="Start time >= (ISO 8601)"),
    start_time_before: Optional[datetime] = Query(None, description="Start time <= (ISO 8601)"),
    duration_min_ms: Optional[float] = Query(None, description="Minimum duration in milliseconds"),
    duration_max_ms: Optional[float] = Query(None, description="Maximum duration in milliseconds"),
    test_run_id: Optional[str] = Query(None, description="Filter by test run ID"),
    test_result_id: Optional[str] = Query(None, description="Filter by test result ID"),
    test_id: Optional[str] = Query(None, description="Filter by test ID"),
    conversation_id: Optional[str] = Query(None, description="Filter by conversation ID"),
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
            "Filter: 'all' (default), 'single_turn' (no conversation_id), "
            "'multi_turn' (has conversation_id)"
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
    limit: int = Query(100, ge=1, le=1000, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
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
    - `environment`: Filter by environment (development, staging, production)
    - `span_name`: Filter by span name (e.g., "ai.llm.invoke")
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

    try:
        # Single DB query returns TraceRow(trace, span_count, total) per row
        rows = crud.query_traces(
            db=db,
            organization_id=organization_id,
            project_id=project_id,
            endpoint_id=endpoint_id,
            root_spans_only=root_spans_only,
            trace_source=trace_source,
            trace_type=trace_type,
            environment=environment,
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
            trace_metrics_status=trace_metrics_status.value if trace_metrics_status else None,
            limit=limit,
            offset=offset,
        )

        total = rows[0].total if rows else 0

        summaries = []
        for row in rows:
            trace = row.trace
            has_errors = trace.status_code == StatusCode.ERROR.value
            total_tokens = trace.total_tokens or 0
            total_cost_usd = 0.0
            total_cost_eur = 0.0
            costs = (trace.enriched_data or {}).get(EnrichedDataKeys.COSTS, {})
            if costs:
                total_cost_usd = costs.get(EnrichedDataKeys.TOTAL_COST_USD, 0.0)
                total_cost_eur = costs.get(EnrichedDataKeys.TOTAL_COST_EUR, 0.0)

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

            # Get trace metrics status if available
            trace_metrics_status_name = None
            if hasattr(trace, "trace_metrics_status") and trace.trace_metrics_status:
                trace_metrics_status_name = trace.trace_metrics_status.name

            # Check review state
            has_reviews = bool(
                trace.trace_reviews
                and isinstance(trace.trace_reviews, dict)
                and trace.trace_reviews.get("reviews")
            )

            summary = TraceSummary(
                trace_id=trace.trace_id,
                project_id=str(trace.project_id),
                environment=trace.environment,
                conversation_id=trace.conversation_id,
                start_time=trace.start_time,
                duration_ms=trace.duration_ms or 0.0,
                span_count=row.span_count,
                root_operation=trace.span_name,
                status_code=trace.status_code,
                test_run_id=str(trace.test_run_id) if trace.test_run_id else None,
                test_result_id=str(trace.test_result_id) if trace.test_result_id else None,
                test_id=str(trace.test_id) if trace.test_id else None,
                endpoint_id=trace_endpoint_id,
                endpoint_name=trace_endpoint_name,
                total_tokens=total_tokens if total_tokens > 0 else None,
                total_cost_usd=total_cost_usd if total_cost_usd > 0 else None,
                total_cost_eur=total_cost_eur if total_cost_eur > 0 else None,
                has_errors=has_errors,
                trace_metrics_status=trace_metrics_status_name,
                has_reviews=has_reviews,
                last_review=trace.last_review,
                matches_review=trace.matches_review,
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


@router.get("/spans/{span_db_id}/lookup")
def lookup_span(
    span_db_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """
    Resolve a span's database UUID to its trace_id and project_id.

    Used for navigation from tasks/comments linked to a Trace entity.
    """
    organization_id, _ = tenant_context
    span = crud.get_trace_by_db_id(db, str(span_db_id), organization_id)
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
    trace_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
) -> TraceDetailResponse:
    """
    Get detailed trace with all spans.

    Returns the complete trace including:
    - All spans in the trace
    - Parent-child relationships
    - Enriched data (costs, anomalies, metadata)

    Args:
        trace_id: OpenTelemetry trace ID (32-char hex)
        project_id: Project ID for access control

    Returns:
        Complete trace details with all spans

    Raises:
        404: Trace not found
    """
    organization_id, user_id = tenant_context

    try:
        # Fetch all spans for trace with eager loading of relationships
        from sqlalchemy.orm import joinedload

        spans = crud.get_trace_by_id(
            db=db,
            trace_id=trace_id,
            project_id=project_id,
            organization_id=organization_id,
            eager_load=["project", "test_run", "test_result", "test"],
        )

        # Additional eager load for endpoint via test_result.test_configuration.endpoint
        # This is done separately since it's a nested relationship
        if spans and spans[0].test_result_id:
            from rhesis.backend.app.models.test_configuration import TestConfiguration
            from rhesis.backend.app.models.test_result import TestResult

            # Fetch test_result with nested eager loading and explicitly update the relationship
            test_result_with_endpoint = (
                db.query(TestResult)
                .filter(TestResult.id == spans[0].test_result_id)
                .options(
                    joinedload(TestResult.test_configuration).joinedload(TestConfiguration.endpoint)
                )
                .first()
            )

            # Explicitly update the relationship instead of relying on identity map
            if test_result_with_endpoint:
                spans[0].test_result = test_result_with_endpoint

        if not spans:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Trace {trace_id} not found"
            )

        # Build proper span tree
        from rhesis.backend.app.services.telemetry.tree_builder import build_span_tree

        root_spans = build_span_tree(spans)

        # Calculate trace-level metrics
        total_duration = max(span.end_time for span in spans) - min(
            span.start_time for span in spans
        )
        total_tokens = sum(span.total_tokens or 0 for span in spans)
        error_count = sum(1 for span in spans if span.status_code == StatusCode.ERROR.value)

        # Extract costs from enriched data
        total_cost = 0.0
        costs = (spans[0].enriched_data or {}).get(EnrichedDataKeys.COSTS, {})
        if costs:
            total_cost = costs.get(EnrichedDataKeys.TOTAL_COST_USD, 0.0)

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
            total_cost_usd=total_cost,
            root_spans=root_spans,
            trace_metrics_status=trace_metrics_status_name,
            trace_reviews=first_span.trace_reviews,
            last_review=first_span.last_review,
            matches_review=first_span.matches_review,
            review_summary=first_span.review_summary,
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
    return crud.get_files_for_entity(
        db, span_db_id, EntityType.TRACE.value, organization_id, user_id
    )


@router.get("/metrics", response_model=TraceMetricsResponse)
def get_metrics(
    project_id: str = Query(..., description="Project ID"),
    environment: Optional[str] = Query(None, description="Environment filter"),
    start_time_after: Optional[datetime] = Query(None, description="Start time >= (ISO 8601)"),
    start_time_before: Optional[datetime] = Query(None, description="Start time <= (ISO 8601)"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
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

    Returns:
        Aggregated metrics
    """
    organization_id, user_id = tenant_context

    try:
        result = crud.get_trace_metrics_aggregated(
            db=db,
            organization_id=organization_id,
            project_id=project_id,
            environment=environment,
            start_time_after=start_time_after,
            start_time_before=start_time_before,
        )

        logger.info(f"Calculated metrics for project {project_id}")
        return TraceMetricsResponse(**result)

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


# ---------------------------------------------------------------------------
# Trace review endpoints
# ---------------------------------------------------------------------------


def _get_status_details(db: Session, status_id: UUID, organization_id: str) -> dict:
    """Fetch status details for a review."""
    status_obj = (
        db.query(models.Status)
        .filter(
            models.Status.id == status_id,
            models.Status.organization_id == organization_id,
        )
        .first()
    )
    if not status_obj:
        raise HTTPException(status_code=404, detail="Status not found")
    return {"status_id": str(status_obj.id), "name": status_obj.name}


def _update_review_metadata(reviews_data: dict, current_user: User, latest_status: dict) -> None:
    """Update metadata when reviews change."""
    now = datetime.now(timezone.utc).isoformat()
    reviews_data["metadata"] = {
        "last_updated_at": now,
        "last_updated_by": {
            "user_id": str(current_user.id),
            "name": current_user.name or current_user.email,
        },
        "total_reviews": len(reviews_data.get("reviews", [])),
        "latest_status": latest_status,
        "summary": f"Last updated by {current_user.name or current_user.email}",
    }


@router.post(
    "/traces/{trace_db_id}/reviews",
    response_model=schemas.ReviewResponse,
)
def add_trace_review(
    trace_db_id: UUID,
    review: schemas.ReviewCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Add a new review to a trace span."""
    organization_id, user_id = tenant_context

    db_trace = crud.get_trace_by_db_id(
        db, trace_db_id=str(trace_db_id), organization_id=organization_id
    )
    if db_trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    status_details = _get_status_details(db, review.status_id, organization_id)

    if not db_trace.trace_reviews:
        db_trace.trace_reviews = {"metadata": {}, "reviews": []}
    elif not isinstance(db_trace.trace_reviews, dict):
        db_trace.trace_reviews = {"metadata": {}, "reviews": []}
    if "reviews" not in db_trace.trace_reviews:
        db_trace.trace_reviews["reviews"] = []

    now = datetime.now(timezone.utc).isoformat()
    new_review = {
        "review_id": str(uuid4()),
        "status": status_details,
        "user": {
            "user_id": str(current_user.id),
            "name": current_user.name or current_user.email,
        },
        "comments": review.comments,
        "created_at": now,
        "updated_at": now,
        "target": {
            "type": review.target.type,
            "reference": review.target.reference,
        },
    }

    db_trace.trace_reviews["reviews"].append(new_review)
    _update_review_metadata(db_trace.trace_reviews, current_user, status_details)
    flag_modified(db_trace, "trace_reviews")

    trace_apply_review_override(
        db_trace,
        review.target.type,
        review.target.reference,
        status_details,
        current_user,
        new_review["review_id"],
    )

    db.flush()
    db.refresh(db_trace)
    db.commit()

    return new_review


@router.put(
    "/traces/{trace_db_id}/reviews/{review_id}",
    response_model=schemas.ReviewResponse,
)
def update_trace_review(
    trace_db_id: UUID,
    review_id: str,
    review: schemas.ReviewUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update an existing trace review."""
    organization_id, user_id = tenant_context

    db_trace = crud.get_trace_by_db_id(
        db, trace_db_id=str(trace_db_id), organization_id=organization_id
    )
    if db_trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    if not db_trace.trace_reviews or "reviews" not in db_trace.trace_reviews:
        raise HTTPException(status_code=404, detail="No reviews found for this trace")

    reviews = db_trace.trace_reviews["reviews"]
    review_to_update = None
    for rev in reviews:
        if rev.get("review_id") == review_id:
            review_to_update = rev
            break
    if review_to_update is None:
        raise HTTPException(status_code=404, detail="Review not found")

    old_target = review_to_update.get("target", {})
    status_changed = False
    if review.status_id is not None:
        status_details = _get_status_details(db, review.status_id, organization_id)
        review_to_update["status"] = status_details
        status_changed = True

    if review.comments is not None:
        review_to_update["comments"] = review.comments

    target_changed = False
    if review.target is not None:
        review_to_update["target"] = {
            "type": review.target.type,
            "reference": review.target.reference,
        }
        target_changed = True

    review_to_update["updated_at"] = datetime.now(timezone.utc).isoformat()
    latest_status = review_to_update["status"]
    _update_review_metadata(db_trace.trace_reviews, current_user, latest_status)
    flag_modified(db_trace, "trace_reviews")

    if status_changed or target_changed:
        if target_changed:
            trace_revert_override(
                db_trace,
                old_target.get("type", ""),
                old_target.get("reference"),
                review_id,
                [],
            )
        trace_apply_review_override(
            db_trace,
            review_to_update["target"]["type"],
            review_to_update["target"].get("reference"),
            review_to_update["status"],
            current_user,
            review_id,
        )

    db.flush()
    db.refresh(db_trace)
    db.commit()

    return review_to_update


@router.delete(
    "/traces/{trace_db_id}/reviews/{review_id}",
    response_model=dict,
)
def delete_trace_review(
    trace_db_id: UUID,
    review_id: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a review from a trace."""
    organization_id, user_id = tenant_context

    db_trace = crud.get_trace_by_db_id(
        db, trace_db_id=str(trace_db_id), organization_id=organization_id
    )
    if db_trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    if not db_trace.trace_reviews or "reviews" not in db_trace.trace_reviews:
        raise HTTPException(status_code=404, detail="No reviews found for this trace")

    reviews = db_trace.trace_reviews["reviews"]
    review_index = None
    for idx, rev in enumerate(reviews):
        if rev.get("review_id") == review_id:
            review_index = idx
            break
    if review_index is None:
        raise HTTPException(status_code=404, detail="Review not found")

    deleted_review = reviews.pop(review_index)

    if reviews:
        latest_review = max(
            reviews,
            key=lambda r: r.get("updated_at", r.get("created_at", "")),
        )
        latest_status = latest_review.get("status", {"status_id": None, "name": "Unknown"})
        _update_review_metadata(db_trace.trace_reviews, current_user, latest_status)
    else:
        db_trace.trace_reviews["metadata"] = {
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_by": {
                "user_id": str(current_user.id),
                "name": current_user.name or current_user.email,
            },
            "total_reviews": 0,
            "latest_status": None,
            "summary": "All reviews removed",
        }

    flag_modified(db_trace, "trace_reviews")

    trace_revert_override(
        db_trace,
        deleted_review.get("target", {}).get("type", ""),
        deleted_review.get("target", {}).get("reference"),
        review_id,
        reviews,
    )

    db.flush()
    db.refresh(db_trace)
    db.commit()

    return {
        "message": "Review deleted successfully",
        "review_id": review_id,
    }
