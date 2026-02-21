"""Deferred conversation linking for first-turn traces.

Problem
-------
For stateful endpoints the first invocation has no conversation_id —
the endpoint generates one in its response.  The backend discovers it
after invocation, but for SDK endpoints (``automatic_tracing=True``)
the OTEL spans are exported asynchronously by the SDK's
BatchSpanProcessor.  By the time the backend tries to stamp the
conversation_id onto the trace, the spans have not arrived yet and
the UPDATE matches 0 rows.

Solution
--------
When the immediate UPDATE finds nothing, the mapping is parked in a
process-level cache.  When ``create_trace_spans()`` later stores the
SDK's spans, the telemetry ingest endpoint calls
``apply_pending_links()`` which pops the mapping from the cache and
applies it.

The cache is protected by a lock and entries expire after
``_PENDING_LINK_TTL`` seconds so stale mappings don't accumulate.

Usage (two call sites)
~~~~~~~~~~~~~~~~~~~~~~
1. ``EndpointService.invoke_endpoint()`` — after invocation, if the
   immediate ``crud.update_conversation_id_for_trace()`` returns 0,
   call ``register_pending_link()``.
2. ``telemetry.ingest_trace()`` — after storing spans, call
   ``apply_pending_links()`` with the stored trace models.
"""

import logging
import threading
import time
from typing import Dict, List, NamedTuple, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models

logger = logging.getLogger(__name__)


class PendingLink(NamedTuple):
    """A deferred conversation-to-trace mapping awaiting span arrival."""

    conversation_id: str
    organization_id: str
    registered_at: float  # time.monotonic() timestamp
    mapped_input: Optional[str] = None
    mapped_output: Optional[str] = None


_lock = threading.Lock()
_pending: Dict[str, PendingLink] = {}

_PENDING_LINK_TTL = 120  # seconds


def register_pending_link(
    trace_id: str,
    conversation_id: str,
    organization_id: str,
    mapped_input: Optional[str] = None,
    mapped_output: Optional[str] = None,
) -> None:
    """Park a conversation link for deferred application.

    Called when ``crud.update_conversation_id_for_trace()`` returns 0
    because the SDK's spans have not been ingested yet.

    Optionally carries mapped I/O so that conversation input/output
    attributes can be backfilled into the span JSONB at the same time.
    """
    with _lock:
        _pending[trace_id] = PendingLink(
            conversation_id=conversation_id,
            organization_id=organization_id,
            registered_at=time.monotonic(),
            mapped_input=mapped_input,
            mapped_output=mapped_output,
        )
        # Evict stale entries while we hold the lock
        cutoff = time.monotonic() - _PENDING_LINK_TTL
        stale = [key for key, link in _pending.items() if link.registered_at < cutoff]
        for key in stale:
            del _pending[key]

    logger.debug(
        f"[CONVERSATION_LINKING] Parked pending link: "
        f"trace_id={trace_id}, conversation_id={conversation_id}"
    )


def backfill_conversation_io(
    db: Session,
    trace_id: str,
    organization_id: str,
    conversation_id: str,
    mapped_input: Optional[str] = None,
    mapped_output: Optional[str] = None,
) -> None:
    """Write mapped I/O attributes into trace spans, deferring if needed.

    Tries an immediate UPDATE on the span rows.  If no rows match
    (SDK spans haven't been ingested yet), parks the data as a pending
    link so ``apply_pending_links()`` can apply it later.

    Call sites: ``SdkEndpointInvoker.invoke()`` (step 9) and
    ``EndpointService.invoke_endpoint()`` (first-turn linking).
    """
    if not mapped_input and not mapped_output:
        return

    count = crud.update_conversation_io_for_trace(
        db=db,
        trace_id=trace_id,
        organization_id=organization_id,
        mapped_input=mapped_input,
        mapped_output=mapped_output,
    )
    if count == 0:
        register_pending_link(
            trace_id=trace_id,
            conversation_id=conversation_id,
            organization_id=organization_id,
            mapped_input=mapped_input,
            mapped_output=mapped_output,
        )


def apply_pending_links(
    db: Session,
    stored_spans: List[models.Trace],
) -> int:
    """Apply parked conversation links for recently stored spans.

    Called by the telemetry ingest endpoint after spans are committed.
    Returns the total number of span rows updated.

    RLS note: The DB session's ``app.current_organization`` may differ
    from the organization that registered the pending link (registered
    during endpoint invocation, applied during telemetry ingest).  We
    switch session context per-link so the UPDATE is visible through
    the ``tenant_isolation`` RLS policy on the ``trace`` table.
    """
    if not stored_spans:
        return 0

    unique_trace_ids = list({s.trace_id for s in stored_spans})

    # Pop matching entries under the lock, then apply outside it
    # to avoid holding the lock during DB operations.
    matched_links: List[tuple[str, PendingLink]] = []
    with _lock:
        for trace_id in unique_trace_ids:
            link = _pending.pop(trace_id, None)
            if link is not None:
                matched_links.append((trace_id, link))

    if not matched_links:
        return 0

    from rhesis.backend.app.database import set_session_variables

    total = 0
    for trace_id, link in matched_links:
        # Ensure RLS context matches the link's organization so the
        # UPDATE can see the trace rows.
        set_session_variables(db, link.organization_id, "")

        count = crud.update_conversation_id_for_trace(
            db, trace_id, link.conversation_id, link.organization_id
        )
        total += count
        logger.info(
            f"[CONVERSATION_LINKING] Applied pending link: "
            f"trace_id={trace_id}, "
            f"conversation_id={link.conversation_id}, "
            f"updated={count} spans"
        )

        # Backfill mapped I/O into span attributes if present
        if link.mapped_input or link.mapped_output:
            io_count = crud.update_conversation_io_for_trace(
                db=db,
                trace_id=trace_id,
                organization_id=link.organization_id,
                mapped_input=link.mapped_input,
                mapped_output=link.mapped_output,
            )
            logger.info(
                f"[CONVERSATION_LINKING] Backfilled I/O for trace_id={trace_id}: {io_count} spans"
            )

    return total
