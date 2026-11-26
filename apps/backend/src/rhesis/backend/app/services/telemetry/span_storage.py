"""Store spans and their trace's enrichment in one transaction.

Both span-storing paths use this: queued ingest (SDK and OTLP routes) and the
endpoint invoker during test runs. Enrichment used to be a separate task that read
the whole trace back, computed costs, and updated every span. Here the trace's
stored spans are read once (that read also serves the duplicate check), enrichment
is computed in memory over stored + new spans, the new rows are inserted with it,
and stored rows get one UPDATE per trace. Ingest holds the trace's advisory lock
for the transaction, so concurrent batches of one trace enrich in turn instead of
racing.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.telemetry import (
    create_trace_spans,
    load_trace_spans,
    lock_traces_for_ingest,
    mark_trace_processed,
)
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate
from rhesis.backend.app.services.telemetry.enrichment.processor import calculate_enrichment

logger = logging.getLogger(__name__)


def store_spans(
    db: Session, spans: List[OTELSpanCreate], organization_id: str
) -> List[models.Trace]:
    """Insert the new spans of *spans*, enriched, and commit. Returns the new rows.

    Holds the traces' ingest lock until the commit, so batches of one trace (from
    ingest workers or the endpoint invoker) are stored and enriched one at a time,
    each seeing the spans the previous one stored.
    """
    trace_ids = {span.trace_id for span in spans}
    lock_traces_for_ingest(db, organization_id, trace_ids)
    existing = load_trace_spans(db, trace_ids)

    def enrich(new_rows: List[models.Trace]) -> None:
        enrich_traces(db, existing, new_rows)

    return create_trace_spans(db, spans, organization_id, existing=existing, before_commit=enrich)


def enrich_traces(db: Session, existing: List[models.Trace], new_rows: List[models.Trace]) -> None:
    """Compute each trace's enrichment over its stored and new spans and write it.

    New rows carry it in their INSERT; stored rows of the trace get one UPDATE. A
    failure leaves the trace unenriched (no cost shown) rather than losing the spans.
    """
    stored_by_trace = defaultdict(list)
    for row in existing:
        stored_by_trace[row.trace_id].append(row)
    new_by_trace = defaultdict(list)
    for row in new_rows:
        new_by_trace[row.trace_id].append(row)

    now = datetime.now(timezone.utc)
    for trace_id, new_spans in new_by_trace.items():
        stored = stored_by_trace.get(trace_id, [])
        try:
            spans = sorted([*stored, *new_spans], key=_start_utc)
            enriched = calculate_enrichment(spans).model_dump(mode="json", exclude_none=True)
        except Exception:
            logger.warning(f"Enrichment failed for trace {trace_id}", exc_info=True)
            continue
        for row in new_spans:
            row.enriched_data = enriched
            row.processed_at = now
        if stored:
            # In the insert's transaction: a commit here would release the ingest lock.
            mark_trace_processed(db, trace_id=trace_id, enriched_data=enriched, commit=False)


def _start_utc(span: models.Trace) -> datetime:
    # Stored rows come back timezone-aware; a new row keeps what the client sent, which
    # may be naive (taken as UTC, as Postgres stores it).
    start = span.start_time
    return start if start.tzinfo else start.replace(tzinfo=timezone.utc)
