"""What happens to a batch of spans right after it is stored.

Linking to test results, applying pending conversation links and files, queueing
turn evaluations, and metering the spans. ``ingest_spans`` runs it inline on the
rows it just stored; it used to be a separate task (``post_ingest_link``) that read
those rows back, which cost a broker round trip, a worker slot, a session and a
query per batch.
"""

import logging
from typing import Dict, List

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

    linked_count = conversation_linked = files_created = 0

    try:
        linked_count = TraceLinkingService(db).link_traces_for_incoming_batch(
            spans=stored_spans, organization_id=organization_id
        )
        if linked_count > 0:
            logger.info(f"Linked {linked_count} traces to test result (traces={unique_trace_ids})")
    except Exception as link_error:
        logger.warning(f"Failed to link traces (traces={unique_trace_ids}): {link_error}")
        logger.debug("Trace linking traceback:", exc_info=True)

    try:
        conversation_linked = apply_pending_conversation_links(db, stored_spans)
        if conversation_linked > 0:
            logger.info(
                f"Applied {conversation_linked} pending conversation "
                f"links (traces={unique_trace_ids})"
            )
    except Exception as conversation_error:
        logger.warning(
            f"Failed to apply conversation links (traces={unique_trace_ids}): {conversation_error}"
        )
        logger.debug("Conversation linking traceback:", exc_info=True)

    try:
        files_created = apply_pending_files(db, stored_spans)
        if files_created > 0:
            logger.info(f"Created {files_created} pending file(s) (traces={unique_trace_ids})")
    except Exception as file_error:
        logger.warning(f"Failed to apply pending files (traces={unique_trace_ids}): {file_error}")
        logger.debug("File linking traceback:", exc_info=True)

    # Linking ran on this session; commit it before queueing work that reads it.
    db.commit()

    queued, _ = EnrichmentService(db).dispatch_for_spans(stored_spans, project_id, organization_id)

    # Summed and queued, never written on `db`: metering must not be able to fail
    # the batch it measures.
    usage_coalescer.add(organization_id, QuotaResource.TRACING_SPANS, len(stored_spans))

    return {
        "linked": linked_count,
        "conversation_linked": conversation_linked,
        "files_created": files_created,
        "evaluations_queued": queued,
    }
