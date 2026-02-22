"""Telemetry router for trace ingestion and queries."""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.constants import EnrichedDataKeys
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
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

# Legacy alias for backward compatibility
TraceResponse = TraceIngestResponse

router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"],
    responses={404: {"description": "Not found"}},
)
logger = logging.getLogger(__name__)


@router.post("/traces", response_model=TraceResponse)
async def ingest_trace(
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
    # The SDK tracer sets rhesis.conversation.input per-span but cannot
    # set rhesis.conversation.output (it only has the raw function
    # return value).  The backend parks the response-mapped output after
    # invocation and injects it here — before the span is stored.
    from rhesis.backend.app.services.telemetry.conversation_linking import (
        apply_pending_conversation_links,
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

    # Store spans and trigger enrichment
    try:
        enrichment_service = EnrichmentService(db)
        stored_spans, async_count, sync_count = enrichment_service.create_and_enrich_spans(
            spans=trace_batch.spans,
            organization_id=organization_id,
            project_id=project_id,
        )

        unique_trace_count = len(set(s.trace_id for s in stored_spans))
        logger.info(
            f"Ingested {len(stored_spans)} spans from "
            f"{unique_trace_count} traces "
            f"(async: {async_count}, sync: {sync_count})"
        )

        # Post-storage linking: apply deferred links now that spans
        # are committed.  Each linking step is independent and must
        # not fail the overall ingestion.
        if stored_spans:
            # 1. Test-result linking (traces <-> test results)
            from rhesis.backend.app.services.telemetry.linking_service import (
                TraceLinkingService,
            )

            linking_service = TraceLinkingService(db)
            try:
                linked_count = linking_service.link_traces_for_incoming_batch(
                    spans=stored_spans,
                    organization_id=organization_id,
                )
                if linked_count > 0:
                    logger.info(
                        f"Linked {linked_count} traces to test result for trace_id={trace_id}"
                    )
            except Exception as link_error:
                logger.warning(f"Failed to link traces for trace_id={trace_id}: {link_error}")
                logger.debug("Trace linking traceback:", exc_info=True)

            # 2. Conversation-id linking (first-turn patching)
            try:
                conversation_linked = apply_pending_conversation_links(db, stored_spans)
                if conversation_linked > 0:
                    logger.info(
                        f"Applied {conversation_linked} pending "
                        f"conversation links for trace_id={trace_id}"
                    )
            except Exception as conversation_error:
                logger.warning(
                    f"Failed to apply conversation links for "
                    f"trace_id={trace_id}: {conversation_error}"
                )
                logger.debug("Conversation linking traceback:", exc_info=True)

        return TraceResponse(
            status="received",
            span_count=len(stored_spans),
            trace_id=trace_id,
        )

    except Exception as e:
        logger.error(f"❌ Failed to store trace {trace_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store trace spans",
        )


@router.get("/traces", response_model=TraceListResponse)
async def list_traces(
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
    - `status_code`: Filter by status (OK, ERROR)
    - `start_time_after`: Filter by start time >= timestamp
    - `start_time_before`: Filter by start time <= timestamp
    - `test_run_id`: Filter by test run ID (for test execution traces)
    - `test_result_id`: Filter by test result ID (for test execution traces)
    - `test_id`: Filter by test ID (for test execution traces)

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
        error_msg = str(e) if str(e) else "Unknown database error"
        logger.error(
            f"Failed to list traces for org {organization_id}: {error_msg}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve traces: {error_msg}",
        )


@router.get("/traces/{trace_id}", response_model=TraceDetailResponse)
async def get_trace(
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

        return TraceDetailResponse(
            trace_id=first_span.trace_id,
            project_id=str(first_span.project_id),  # Convert UUID to string
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
            # Add relationship objects
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
        error_msg = str(e) if str(e) else "Unknown database error"
        logger.error(
            f"Failed to retrieve trace {trace_id}: {error_msg}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trace details: {error_msg}",
        )


@router.get("/metrics", response_model=TraceMetricsResponse)
async def get_metrics(
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
        # Query all matching spans (no default time filter - controlled by frontend)
        spans_with_counts = crud.query_traces(
            db=db,
            organization_id=organization_id,
            project_id=project_id,
            root_spans_only=False,  # Metrics need all spans for accurate calculations
            trace_source=TraceSource.ALL,  # Include all trace sources
            environment=environment,
            start_time_after=start_time_after,
            start_time_before=start_time_before,
            limit=10000,  # Large limit for metrics calculation
            offset=0,
        )

        # Extract just the Trace objects (discard span_count and total)
        spans = [row.trace for row in spans_with_counts]

        if not spans:
            return TraceMetricsResponse(
                total_traces=0,
                total_spans=0,
                total_tokens=0,
                total_cost_usd=0,
                error_rate=0,
                avg_duration_ms=0,
                p50_duration_ms=0,
                p95_duration_ms=0,
                p99_duration_ms=0,
                operation_breakdown={},
            )

        # Count unique traces
        trace_ids = set(span.trace_id for span in spans)
        total_traces = len(trace_ids)
        total_spans = len(spans)

        # Calculate token metrics (LLM spans only)
        total_tokens = sum(span.total_tokens or 0 for span in spans)

        # Calculate cost metrics
        total_cost = 0.0
        for span in spans:
            costs = (span.enriched_data or {}).get(EnrichedDataKeys.COSTS, {})
            if costs:
                total_cost += costs.get(EnrichedDataKeys.TOTAL_COST_USD, 0.0)

        # Calculate error rate
        error_count = sum(1 for span in spans if span.status_code == StatusCode.ERROR.value)
        error_rate = error_count / total_spans if total_spans > 0 else 0

        # Calculate latency percentiles
        durations = sorted(span.duration_ms or 0.0 for span in spans)

        def percentile(values: List[float], p: int) -> float:
            if not values:
                return 0.0
            index = int((p / 100) * len(values))
            index = min(index, len(values) - 1)
            return values[index]

        p50_duration = percentile(durations, 50)
        p95_duration = percentile(durations, 95)
        p99_duration = percentile(durations, 99)
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Operation type breakdown
        operation_breakdown = {}
        for span in spans:
            op_type = span.operation_type or "unknown"
            operation_breakdown[op_type] = operation_breakdown.get(op_type, 0) + 1

        logger.info(f"Calculated metrics for project {project_id}")

        return TraceMetricsResponse(
            total_traces=total_traces,
            total_spans=total_spans,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 6),
            error_rate=round(error_rate, 4),
            avg_duration_ms=round(avg_duration, 2),
            p50_duration_ms=round(p50_duration, 2),
            p95_duration_ms=round(p95_duration, 2),
            p99_duration_ms=round(p99_duration, 2),
            operation_breakdown=operation_breakdown,
        )

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
        error_msg = str(e) if str(e) else "Unknown database error"
        logger.error(
            f"Failed to calculate metrics for project {project_id}: {error_msg}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trace metrics: {error_msg}",
        )
