"""Trace enrichment processor.

Provides enrichment logic for calculating costs, detecting anomalies,
and extracting metadata from traces. Used by both sync and async paths.
"""

import logging
from typing import List, Optional

from rhesis.telemetry.schemas import StatusCode
from sqlalchemy.orm import Session

from rhesis.backend.app.crud import get_trace_by_id, mark_trace_processed
from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.schemas.enrichment import EnrichedTraceData, TraceMetrics
from rhesis.backend.app.services.telemetry.enrichment.core import (
    calculate_token_costs,
    detect_anomalies,
    extract_metadata,
)

logger = logging.getLogger(__name__)


class TraceEnricher:
    """Service for trace enrichment."""

    def __init__(self, db: Session):
        """
        Initialize enricher.

        Args:
            db: Database session
        """
        self.db = db

    def enrich_trace(
        self, trace_id: str, project_id: str, organization_id: str
    ) -> Optional[EnrichedTraceData]:
        """
        Enrich a trace with costs, anomalies, and metadata.

        First checks if enrichment is already cached. If not, calculates
        and caches the results.

        This method is used by both:
        - Async Celery tasks (production with workers)
        - Sync fallback (development without workers)

        Args:
            trace_id: OpenTelemetry trace ID
            project_id: Project ID for access control
            organization_id: Organization ID for multi-tenant security

        Returns:
            EnrichedTraceData Pydantic model
        """
        # Fetch all spans for this trace
        spans = get_trace_by_id(
            self.db, trace_id=trace_id, project_id=project_id, organization_id=organization_id
        )

        if not spans:
            logger.warning(f"No spans found for trace {trace_id}")
            return None

        # Smart cache: return cached enrichment only when no new spans have
        # arrived since the last enrichment pass.  This allows progressive
        # re-enrichment as child spans (LLM calls, costs, etc.) arrive after
        # the root span, while avoiding redundant work once everything is
        # processed.
        #
        # `processed_at` is set on every span row by mark_trace_processed.
        # Newly stored spans default to processed_at=None, so any span with
        # processed_at=None means new data has arrived that warrants a re-run.
        root_span = spans[0]  # ordered by start_time asc, so this is the root
        if root_span.enriched_data and root_span.processed_at:
            unprocessed = [s for s in spans if s.processed_at is None]
            if not unprocessed:
                logger.debug(
                    f"Using cached enrichment for trace {trace_id} "
                    f"(all {len(spans)} spans processed)"
                )
                return EnrichedTraceData(**root_span.enriched_data)
            logger.debug(
                f"Re-enriching trace {trace_id}: "
                f"{len(unprocessed)} new span(s) since last enrichment"
            )

        # Calculate enrichment (returns Pydantic model)
        logger.debug(f"Enriching trace {trace_id}")
        enriched_model = self._calculate_enrichment(spans)

        # Convert to dict for database storage only
        enriched_data = enriched_model.model_dump(mode="json", exclude_none=True)

        # Cache enrichment in database
        mark_trace_processed(self.db, trace_id=trace_id, enriched_data=enriched_data)

        # Return the Pydantic model (not the dict)
        return enriched_model

    def _calculate_enrichment(self, spans: List[Trace]) -> EnrichedTraceData:
        """
        Calculate enrichment for trace spans.

        Args:
            spans: List of spans in the trace

        Returns:
            EnrichedTraceData Pydantic model
        """
        # Calculate costs (returns TokenCosts model or None)
        cost_data = calculate_token_costs(spans)

        # Detect anomalies (returns List[Anomaly] or None)
        anomalies = detect_anomalies(spans)

        # Extract metadata (returns dict)
        metadata = extract_metadata(spans)

        # Calculate trace-level metrics (use semantic layer constant for status)
        metrics = TraceMetrics(
            total_duration_ms=sum(span.duration_ms for span in spans if span.duration_ms),
            span_count=len(spans),
            error_count=sum(1 for span in spans if span.status_code == StatusCode.ERROR.value),
        )

        # Build EnrichedTraceData model
        return EnrichedTraceData(
            costs=cost_data,
            anomalies=anomalies,
            metrics=metrics,
            models_used=metadata.get("models_used"),
            tools_used=metadata.get("tools_used"),
            operation_types=metadata.get("operation_types"),
            root_operation=metadata.get("root_operation"),
        )
