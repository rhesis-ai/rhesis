"""Enrichment orchestration service.

Handles the coordination between async and sync enrichment strategies.
"""

import logging
import time
from typing import TYPE_CHECKING, List, Set

from sqlalchemy.orm import Session

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


def are_workers_recently_available() -> bool:
    """Return True if a recent worker-availability check was positive (cache-only, no ping)."""
    now = time.monotonic()
    age = now - _worker_cache["checked_at"]
    return _worker_cache["available"] is True and age < _WORKER_CACHE_TTL


def check_workers_available() -> bool:
    """Check worker availability, using cached result when fresh (TTL=300s).

    Unlike ``are_workers_recently_available`` this will perform a Celery
    ping when the cache is cold or expired, so callers can rely on an
    accurate result even on a freshly started process.
    """
    now = time.monotonic()
    age = now - _worker_cache["checked_at"]

    if _worker_cache["available"] is not None and age < _WORKER_CACHE_TTL:
        return _worker_cache["available"]

    try:
        from rhesis.backend.worker import app as celery_app

        inspect = celery_app.control.inspect(timeout=1.0)
        ping_result = inspect.ping()

        if not ping_result:
            _worker_cache["available"] = False
            _worker_cache["checked_at"] = time.monotonic()
            return False

        logger.debug(f"Found {len(ping_result)} available worker(s): {list(ping_result.keys())}")
        _worker_cache["available"] = True
        _worker_cache["checked_at"] = time.monotonic()
        return True

    except Exception as e:
        logger.debug(f"Worker availability check failed: {e}")
        _worker_cache["available"] = False
        _worker_cache["checked_at"] = time.monotonic()
        return False


class EnrichmentService:
    """Service for orchestrating trace enrichment with async/sync fallback."""

    def __init__(self, db: Session):
        """Initialize the enrichment service."""
        self.db = db

    def _check_workers_available(self) -> bool:
        """Check if Celery workers are available to process telemetry tasks.

        Delegates to the module-level ``check_workers_available()`` which
        uses a TTL-cached Celery ping.
        """
        return check_workers_available()

    def enqueue_enrichment(
        self,
        trace_id: str,
        project_id: str,
        organization_id: str,
        workers_available: bool | None = None,
        root_span_id: str | None = None,
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
            root_span_id: DB primary key of the root span that triggered
                this enrichment.  Passed through to
                ``evaluate_turn_trace_metrics`` so it evaluates the
                correct span in multi-turn conversations.

        Returns:
            True if async task was enqueued, False if sync fallback was used
        """
        # Check if workers are available (use cached result if provided)
        if workers_available is None:
            workers_available = self._check_workers_available()

        if workers_available:
            try:
                workflow = build_enrichment_chain(
                    trace_id,
                    project_id,
                    organization_id,
                    root_span_id=root_span_id,
                )
                result = workflow.apply_async()
                logger.debug(
                    f"Enqueued async pipeline (enrich -> evaluate) "
                    f"for trace {trace_id} (task: {result.id})"
                )
                return True

            except Exception as e:
                logger.warning(
                    f"Async enrichment failed for trace {trace_id}, using sync fallback: {e}"
                )
        else:
            logger.info(f"No Celery workers available, using sync enrichment for trace {trace_id}")

        # Fall back to synchronous enrichment (cost calculation, anomaly
        # detection).  Metric evaluation (LLM calls) is skipped -- it
        # requires Celery workers and should never run in-process.
        try:
            enricher = TraceEnricher(self.db)
            enriched_data = enricher.enrich_trace(trace_id, project_id, organization_id)
            if enriched_data:
                logger.info(f"Completed sync enrichment for trace {trace_id}")
                logger.warning(
                    f"Trace metrics evaluation skipped for {trace_id} "
                    f"(requires Celery workers for async processing)"
                )
            else:
                logger.warning(f"Sync enrichment returned no data for trace {trace_id}")
            return False
        except Exception as sync_error:
            # Log but don't fail the ingestion
            logger.error(
                f"Sync enrichment failed for trace {trace_id}: {sync_error}", exc_info=True
            )
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
        async_count = 0
        sync_count = 0

        # Check worker availability once before the loop to avoid N×3 second timeout
        # when workers are unavailable (prevents batch processing delays)
        workers_available = self._check_workers_available()

        for trace_id in trace_ids:
            if self.enqueue_enrichment(trace_id, project_id, organization_id, workers_available):
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

        Used by the endpoint invocation path (``services/invokers/tracing.py``),
        **not** by the main telemetry ingestion router which handles storage and
        enrichment dispatch separately.

        Dispatches one enrichment chain **per root span** so that each turn
        in a multi-turn conversation gets its own evaluation task keyed by
        the root span's DB primary key.  Trace IDs that only contain child
        spans in this batch still get an enrichment-only dispatch.

        Args:
            spans: List of OTEL spans to create
            organization_id: Organization ID for tenant isolation
            project_id: Project ID for access control

        Returns:
            Tuple of (stored_spans, async_count, sync_count)
        """
        from rhesis.backend.app import crud

        stored_spans = crud.create_trace_spans(self.db, spans, organization_id)

        if not stored_spans:
            logger.warning("No spans were stored")
            return [], 0, 0

        workers_available = self._check_workers_available()
        async_count = 0
        sync_count = 0
        dispatched_traces: Set[str] = set()

        root_spans = [s for s in stored_spans if s.parent_span_id is None]
        for root_span in root_spans:
            if self.enqueue_enrichment(
                root_span.trace_id,
                project_id,
                organization_id,
                workers_available=workers_available,
                root_span_id=str(root_span.id),
            ):
                async_count += 1
            else:
                sync_count += 1
            dispatched_traces.add(root_span.trace_id)

        child_only_traces = {s.trace_id for s in stored_spans} - dispatched_traces
        for trace_id in child_only_traces:
            if self.enqueue_enrichment(trace_id, project_id, organization_id, workers_available):
                async_count += 1
            else:
                sync_count += 1

        logger.debug(
            f"Created {len(stored_spans)} spans, dispatched "
            f"{len(root_spans)} root-span chains + "
            f"{len(child_only_traces)} child-only enrichments "
            f"(async: {async_count}, sync: {sync_count})"
        )

        return stored_spans, async_count, sync_count


def build_enrichment_chain(
    trace_id: str,
    project_id: str,
    organization_id: str,
    root_span_id: str | None = None,
):
    """Build the Celery chain for trace enrichment followed by metric evaluation.

    Args:
        root_span_id: DB primary key of the root span to evaluate.
            Threaded through to ``evaluate_turn_trace_metrics`` so it
            targets the exact span rather than querying for the latest
            root span by ``trace_id`` (which causes missed turns in
            multi-turn conversations).
    """
    from celery import chain

    from rhesis.backend.tasks.telemetry.enrich import enrich_trace_async
    from rhesis.backend.tasks.telemetry.evaluate import evaluate_turn_trace_metrics

    return chain(
        enrich_trace_async.si(trace_id, project_id, organization_id),
        evaluate_turn_trace_metrics.si(
            trace_id,
            project_id,
            organization_id,
            root_span_id=root_span_id,
        ),
    )
