"""Enrichment orchestration service.

Handles the coordination between async and sync enrichment strategies.
"""

import logging
from typing import TYPE_CHECKING, List, Set

from sqlalchemy.orm import Session

from rhesis.backend.app.services.telemetry.enricher import TraceEnricher

if TYPE_CHECKING:
    from rhesis.backend.app import models
    from rhesis.sdk.telemetry.schemas import OTELSpanCreate

logger = logging.getLogger(__name__)


class EnrichmentService:
    """Service for orchestrating trace enrichment with async/sync fallback."""

    def __init__(self, db: Session):
        """Initialize the enrichment service."""
        self.db = db

    def _check_workers_available(self) -> bool:
        """
        Check if Celery workers are available to process telemetry tasks.

        Returns:
            True if workers are available, False otherwise
        """
        try:
            from rhesis.backend.worker import app as celery_app

            # Use ping with 3 second timeout - more reliable for solo pool workers
            # Solo pool workers process tasks sequentially, so stats() may timeout
            # while ping() is faster and gets prioritized
            inspect = celery_app.control.inspect(timeout=3.0)

            # Ping is faster and works better with solo pool
            ping_result = inspect.ping()

            if not ping_result:
                return False

            # If we can ping workers, they're available
            logger.debug(
                f"Found {len(ping_result)} available worker(s): {list(ping_result.keys())}"
            )
            return True

        except Exception as e:
            logger.debug(f"Worker availability check failed: {e}")
            return False

    def enqueue_enrichment(
        self, trace_id: str, project_id: str, workers_available: bool | None = None
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
            workers_available: Optional cached worker availability check result.
                             If None, will check on this call.

        Returns:
            True if async task was enqueued, False if sync fallback was used
        """
        # Check if workers are available (use cached result if provided)
        if workers_available is None:
            workers_available = self._check_workers_available()

        if workers_available:
            try:
                from rhesis.backend.tasks.telemetry.enrich import enrich_trace_async

                # Try to enqueue async task
                result = enrich_trace_async.delay(trace_id, project_id)
                logger.debug(f"Enqueued async enrichment for trace {trace_id} (task: {result.id})")
                return True

            except Exception as e:
                logger.warning(
                    f"Async enrichment failed for trace {trace_id}, using sync fallback: {e}"
                )
        else:
            logger.info(f"No Celery workers available, using sync enrichment for trace {trace_id}")

        # Fall back to synchronous enrichment
        try:
            enricher = TraceEnricher(self.db)
            enriched_data = enricher.enrich_trace(trace_id, project_id)
            if enriched_data:
                logger.info(f"Completed sync enrichment for trace {trace_id}")
            else:
                logger.warning(f"Sync enrichment returned no data for trace {trace_id}")
            return False
        except Exception as sync_error:
            # Log but don't fail the ingestion
            logger.error(
                f"Sync enrichment failed for trace {trace_id}: {sync_error}", exc_info=True
            )
            return False

    def enrich_traces(self, trace_ids: Set[str], project_id: str) -> tuple[int, int]:
        """
        Enrich multiple traces using async/sync fallback strategy.

        Args:
            trace_ids: Set of trace IDs to enrich
            project_id: Project ID for access control

        Returns:
            Tuple of (async_count, sync_count)
        """
        async_count = 0
        sync_count = 0

        # Check worker availability once before the loop to avoid N×3 second timeout
        # when workers are unavailable (prevents batch processing delays)
        workers_available = self._check_workers_available()

        for trace_id in trace_ids:
            if self.enqueue_enrichment(trace_id, project_id, workers_available):
                async_count += 1
            else:
                sync_count += 1

        return async_count, sync_count

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
        async_count, sync_count = self.enrich_traces(unique_traces, project_id)

        logger.debug(
            f"Created {len(stored_spans)} spans from {len(unique_traces)} traces "
            f"(async enrichment: {async_count}, sync: {sync_count})"
        )

        return stored_spans, async_count, sync_count
