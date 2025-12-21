"""Telemetry router for trace ingestion and queries."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.schemas.telemetry import (
    OTELTraceBatch,
    TraceIngestResponse,
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

        # TODO (WP5): Enqueue background processing
        # from rhesis.backend.tasks.telemetry import process_trace_async
        # process_trace_async.delay(trace_id=trace_id, project_id=project_id)

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
