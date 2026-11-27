"""What happens to a batch of spans right after it is stored.

Linking to test results, applying pending conversation links and files, queueing
turn evaluations, and metering the spans. ``ingest_spans`` runs it inline on the
rows it just stored.
"""

import logging
from typing import Callable, Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services import usage_coalescer

logger = logging.getLogger(__name__)


def process_stored_spans(
    db: Session,
    stored_spans: List[models.Trace],
    unique_trace_ids: List[str],
    organization_id: str,
    project_id: str,
) -> Dict[str, int]:
    """Link, queue evaluations for, and meter freshly stored spans.

    Each step logs its own failure and the rest still run: the spans are stored, and
    a linking problem must not stop their evaluation or metering.
    """
    from rhesis.backend.app.services.telemetry.conversation_linking import (
        apply_pending_conversation_links,
        apply_pending_files,
    )
    from rhesis.backend.app.services.telemetry.enrichment import EnrichmentService
    from rhesis.backend.app.services.telemetry.linking_service import TraceLinkingService

    # Metered first, summed and queued, never written on `db`: metering must not be able
    # to fail the batch it measures.
    usage_coalescer.add(organization_id, QuotaResource.TRACING_SPANS, len(stored_spans))

    linked_count = _step(
        db,
        "link traces to test results",
        unique_trace_ids,
        lambda: TraceLinkingService(db).link_traces_for_incoming_batch(
            spans=stored_spans, organization_id=organization_id
        ),
    )
    conversation_linked = _step(
        db,
        "apply pending conversation links",
        unique_trace_ids,
        lambda: apply_pending_conversation_links(db, stored_spans),
    )
    files_created = _step(
        db,
        "apply pending files",
        unique_trace_ids,
        lambda: apply_pending_files(db, stored_spans),
    )

    queued = 0
    try:
        queued, _ = EnrichmentService(db).dispatch_for_spans(
            stored_spans, project_id, organization_id
        )
    except Exception:
        db.rollback()
        logger.warning(f"Failed to queue evaluations (traces={unique_trace_ids})", exc_info=True)

    return {
        "linked": linked_count,
        "conversation_linked": conversation_linked,
        "files_created": files_created,
        "evaluations_queued": queued,
    }


def _step(db: Session, what: str, trace_ids: List[str], run: Callable[[], int]) -> int:
    """Run one linking step and commit what it wrote; on failure roll back and go on.

    Committed per step, so a later failure cannot undo an earlier step's writes. A
    step that changed nothing leaves the transaction to the next one.
    """
    try:
        count = run()
        if count:
            db.commit()
            logger.info(f"{what}: {count} (traces={trace_ids})")
        return count
    except Exception:
        db.rollback()
        logger.warning(f"Failed to {what} (traces={trace_ids})", exc_info=True)
        return 0
