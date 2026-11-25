"""Queueing the evaluation of freshly stored traces.

Two paths store spans: queued ingest (``post_ingest.process_stored_spans``, for the
SDK and OTLP routes) and the endpoint invoker during test runs
(``create_and_enrich_spans``). Both enrich the spans as they store them
(``span_storage.store_spans``), so what is left is one evaluation task per root span,
and only for projects that assigned trace metrics.
"""

import logging
from typing import TYPE_CHECKING, Any, List

from sqlalchemy.orm import Session

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services import usage_coalescer
from rhesis.backend.app.services.async_service import AsyncService
from rhesis.backend.app.services.telemetry.trace_metrics_config import (
    evaluation_enabled,
    project_trace_metrics_config,
)
from rhesis.sdk.telemetry.reported_spans import REPORTED, SOURCE_ATTRIBUTE

if TYPE_CHECKING:
    from rhesis.backend.app import models
    from rhesis.backend.app.schemas.telemetry import OTELSpanCreate

logger = logging.getLogger(__name__)


class EnrichmentService(AsyncService[None]):
    """Stores and enriches spans, and queues their turn evaluations."""

    def __init__(self, db: Session):
        super().__init__()
        self.db = db

    def _execute_sync(
        self,
        trace_id: str,
        project_id: str,
        organization_id: str,
        root_span_id: str | None = None,
    ) -> None:
        """Broker unreachable: evaluation makes LLM calls, so it never runs in-process."""
        logger.warning(
            f"Trace metrics evaluation skipped for {trace_id} (broker unavailable; "
            f"the spans are stored and enriched)"
        )

    def _enqueue_async(
        self,
        trace_id: str,
        project_id: str,
        organization_id: str,
        root_span_id: str | None = None,
    ) -> Any:
        result = build_turn_evaluation(
            trace_id, project_id, organization_id, root_span_id=root_span_id
        ).apply_async()
        logger.debug(f"Enqueued evaluation for trace {trace_id} (task: {result.id})")
        return result

    def enqueue_evaluation(
        self,
        trace_id: str,
        project_id: str,
        organization_id: str,
        root_span_id: str | None = None,
    ) -> bool:
        """Queue one turn's evaluation. False when the broker was unreachable."""
        try:
            was_async, _ = self.execute_with_fallback(
                trace_id, project_id, organization_id, root_span_id=root_span_id
            )
            return was_async
        except Exception as e:
            logger.error(f"Queueing evaluation failed for trace {trace_id}: {e}", exc_info=True)
            return False

    def dispatch_for_spans(
        self,
        stored_spans: List["models.Trace"],
        project_id: str,
        organization_id: str,
    ) -> tuple[int, int]:
        """Queue an evaluation per root span. Returns ``(queued, not_queued)``.

        One task per root span, keyed by its primary key, so each turn of a
        conversation is evaluated on its own. Nothing is queued for a project
        without trace metrics: that task would only have found nothing to do.
        """
        root_spans = [s for s in stored_spans if s.parent_span_id is None]
        if not root_spans:
            return 0, 0
        config = project_trace_metrics_config(self.db, organization_id, project_id)
        if not evaluation_enabled(config):
            return 0, 0

        queued = not_queued = 0
        for root_span in root_spans:
            if self.enqueue_evaluation(
                root_span.trace_id, project_id, organization_id, root_span_id=str(root_span.id)
            ):
                queued += 1
            else:
                not_queued += 1
        return queued, not_queued

    def create_and_enrich_spans(
        self,
        spans: List["OTELSpanCreate"],
        organization_id: str,
        project_id: str,
    ) -> tuple[List["models.Trace"], int, int]:
        """Store spans from the endpoint invoker, enriched, and queue their evaluations.

        Returns:
            Tuple of (stored_spans, queued, not_queued)
        """
        # Imported here: span_storage imports this package's processor, and this module
        # is loaded by the package __init__.
        from rhesis.backend.app.services.telemetry.span_storage import store_spans

        stored_spans = store_spans(self.db, spans, organization_id)

        if not stored_spans:
            logger.warning("No spans were stored")
            return [], 0, 0

        # Metered here as well as in queued ingest: these are the two paths that create
        # Trace rows, and they are disjoint (this one is the invoker, that one inbound
        # telemetry), so no span is counted twice. Placed right after the rows are
        # persisted: storing them is what makes them billable, and a failure to queue
        # an evaluation below should not drop the count. Spans made from what a
        # response reported are Rhesis's own derivation, not the endpoint's telemetry,
        # so they are not metered.
        metered = [
            span
            for span in stored_spans
            if (span.attributes or {}).get(SOURCE_ATTRIBUTE) != REPORTED
        ]
        usage_coalescer.add(organization_id, QuotaResource.TRACING_SPANS, len(metered))

        queued, not_queued = self.dispatch_for_spans(stored_spans, project_id, organization_id)
        return stored_spans, queued, not_queued


def build_turn_evaluation(
    trace_id: str,
    project_id: str,
    organization_id: str,
    root_span_id: str | None = None,
):
    """The task signature that evaluates one stored turn.

    Args:
        root_span_id: DB primary key of the root span to evaluate, so the task targets
            that exact turn rather than the latest root span of the trace.
    """
    from rhesis.backend.jobs.telemetry.evaluate import evaluate_turn_trace_metrics

    return evaluate_turn_trace_metrics.si(
        trace_id, project_id, organization_id, root_span_id=root_span_id
    )
