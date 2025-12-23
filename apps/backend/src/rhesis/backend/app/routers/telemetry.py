"""Telemetry router for trace ingestion and queries."""

import logging
from typing import Set

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.schemas.telemetry import (
    OTELTraceBatch,
    TraceIngestResponse,
)
from rhesis.backend.app.services.telemetry.enricher import TraceEnricher

# Legacy alias for backward compatibility
TraceResponse = TraceIngestResponse

router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"],
    responses={404: {"description": "Not found"}},
)
logger = logging.getLogger(__name__)


def enqueue_enrichment(trace_id: str, project_id: str, db: Session) -> bool:
    """
    Try to enqueue async enrichment. Fall back to sync if workers unavailable.

    Args:
        trace_id: Trace ID to enrich
        project_id: Project ID for access control
        db: Database session (for sync fallback)

    Returns:
        True if async task was enqueued, False if sync fallback was used
    """
    try:
        from rhesis.backend.tasks.telemetry.enrich import enrich_trace_async

        # Try to enqueue async task
        result = enrich_trace_async.delay(trace_id, project_id)
        logger.debug(f"Enqueued async enrichment for trace {trace_id} (task: {result.id})")
        return True

    except Exception as e:
        # Worker not available (development mode, Redis down, etc.)
        logger.warning(
            f"Async enrichment unavailable for trace {trace_id}, using sync fallback: {e}"
        )

        # Fall back to synchronous enrichment
        try:
            enricher = TraceEnricher(db)
            enricher.enrich_trace(trace_id, project_id)
            logger.info(f"Completed sync enrichment for trace {trace_id}")
            return False
        except Exception as sync_error:
            # Log but don't fail the ingestion
            logger.error(
                f"Sync enrichment failed for trace {trace_id}: {sync_error}", exc_info=True
            )
            return False


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

    # Store spans in database
    try:
        stored_spans = crud.create_trace_spans(
            db=db,
            spans=trace_batch.spans,
            organization_id=organization_id,
        )

        logger.debug(f"✅ Stored {len(stored_spans)} spans for trace {trace_id}")

        # Enrich all unique traces (async preferred, sync fallback)
        unique_traces: Set[str] = {span.trace_id for span in stored_spans}
        async_count = 0
        sync_count = 0

        for tid in unique_traces:
            if enqueue_enrichment(tid, project_id, db):
                async_count += 1
            else:
                sync_count += 1

        logger.info(
            f"Ingested {len(stored_spans)} spans from {len(unique_traces)} traces "
            f"(async: {async_count}, sync: {sync_count})"
        )

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
