"""Trace enrichment: costs, anomalies, metadata and metrics for a trace's spans."""

import logging
from typing import List

from rhesis.telemetry.schemas import StatusCode

from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.schemas.enrichment import EnrichedTraceData, TraceMetrics
from rhesis.backend.app.services.telemetry.enrichment.core import (
    calculate_token_costs,
    detect_anomalies,
    extract_metadata,
)

logger = logging.getLogger(__name__)


def calculate_enrichment(spans: List[Trace]) -> EnrichedTraceData:
    """
    Calculate enrichment for a trace's spans: costs, anomalies, metadata, metrics.

    Pure: no database access. Ingest runs it over the stored and incoming spans of a
    trace before inserting (``span_storage.store_spans``).

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
