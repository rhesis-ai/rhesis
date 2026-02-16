"""Enrichment orchestration service.

Handles the coordination between async and sync enrichment strategies.
"""

import logging
from typing import TYPE_CHECKING, Any, List, Set

from sqlalchemy.orm import Session

from rhesis.backend.app.services.async_service import AsyncService
from rhesis.backend.app.services.telemetry.enrichment.processor import TraceEnricher

if TYPE_CHECKING:
    from rhesis.backend.app import models
    from rhesis.sdk.telemetry.schemas import OTELSpanCreate

logger = logging.getLogger(__name__)

# Module-level cache for worker availability to avoid repeated ~3s Celery pings.
# Each inspect.ping() call takes ~3s even when workers are available. Caching the
# result avoids paying that cost on every single endpoint invocation.
_worker_cache: dict = {"available": None, "checked_at": 0.0}
_WORKER_CACHE_TTL = 300.0  # seconds


class EnrichmentService(AsyncService[dict]):
    """Service for orchestrating trace enrichment with async/sync fallback."""

    def __init__(self, db: Session):
        """Initialize the enrichment service."""
        super().__init__()
        self.db = db

    def _execute_sync(self, trace_id: str, project_id: str, organization_id: str) -> dict | None:
        """
        Synchronous enrichment (development fallback).

        Args:
            trace_id: Trace ID to enrich
            project_id: Project ID for access control
            organization_id: Organization ID for multi-tenant security

        Uses a module-level cache (TTL=60s) to avoid the ~3s Celery
        inspect.ping() cost on every endpoint invocation.

        Returns:
            Enriched trace data or None if enrichment failed
        """
        enricher = TraceEnricher(self.db)
        enriched_data = enricher.enrich_trace(trace_id, project_id, organization_id)
        if enriched_data:
            logger.info(f"Completed sync enrichment for trace {trace_id}")
        else:
            logger.warning(f"Sync enrichment returned no data for trace {trace_id}")
        return enriched_data

    def _enqueue_async(self, trace_id: str, project_id: str, organization_id: str) -> Any:
        """
        Enqueue async enrichment task.

        Args:
            trace_id: Trace ID to enrich
            project_id: Project ID for access control
            organization_id: Organization ID for multi-tenant security

        Returns:
            Celery AsyncResult
        """
        from rhesis.backend.tasks.telemetry.enrich import enrich_trace_async

        result = enrich_trace_async.delay(trace_id, project_id, organization_id)
        logger.debug(f"Enqueued async enrichment for trace {trace_id} (task: {result.id})")
        return result

    def enqueue_enrichment(
        self,
        trace_id: str,
        project_id: str,
        organization_id: str,
        workers_available: bool | None = None,
    ) -> bool:
        """
        Try to enqueue async enrichment. Fall back to sync if workers unavailable.

        This function implements a robust fallback strategy:
        1. Check if workers are available (or use cached result)
        2. If yes, try async enrichment (optimal for production)
        3. If no workers or async fails, fall back to sync (development-friendly)

        Args:
            trace_id: Trace ID to enrich
            project_id: Project ID for access control
            organization_id: Organization ID for multi-tenant security
            workers_available: Optional cached worker availability check result.
                             If None, will check on this call.

        Returns:
            True if async task was enqueued, False if sync fallback was used
        """
        try:
            was_async, _ = self.execute_with_fallback(
                trace_id, project_id, organization_id, workers_available=workers_available
            )
            return was_async
        except Exception as e:
            # Log but don't fail the ingestion
            logger.error(f"Enrichment failed for trace {trace_id}: {e}", exc_info=True)
            return False

    def enrich_traces(
        self, trace_ids: Set[str], project_id: str, organization_id: str
    ) -> tuple[int, int]:
        """
        Enrich multiple traces using async/sync fallback strategy.

        Args:
            trace_ids: Set of trace IDs to enrich
            project_id: Project ID for access control
            organization_id: Organization ID for multi-tenant security

        Returns:
            Tuple of (async_count, sync_count)
        """
        items = [((trace_id, project_id, organization_id), {}) for trace_id in trace_ids]
        return self.batch_execute(items)

    def create_and_enrich_spans(
        self,
        spans: List["OTELSpanCreate"],
        organization_id: str,
        project_id: str,
    ) -> tuple[List["models.Trace"], int, int]:
        """
        Create trace spans and automatically trigger enrichment.

        This helper consolidates the pattern of:
        1. Creating spans in database
        2. Extracting unique trace IDs
        3. Triggering async/sync enrichment

        Args:
            spans: List of OTEL spans to create
            organization_id: Organization ID for tenant isolation
            project_id: Project ID for access control

        Returns:
            Tuple of (stored_spans, async_count, sync_count)
        """
        from rhesis.backend.app import crud

        # Create spans in database
        stored_spans = crud.create_trace_spans(self.db, spans, organization_id)

        if not stored_spans:
            logger.warning("No spans were stored")
            return [], 0, 0

        # Extract unique trace IDs
        unique_traces: Set[str] = {span.trace_id for span in stored_spans}

        # Trigger enrichment (async preferred, sync fallback)
        async_count, sync_count = self.enrich_traces(unique_traces, project_id, organization_id)

        logger.debug(
            f"Created {len(stored_spans)} spans from {len(unique_traces)} traces "
            f"(async enrichment: {async_count}, sync: {sync_count})"
        )

        return stored_spans, async_count, sync_count
