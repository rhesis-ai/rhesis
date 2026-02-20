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
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_pending: Dict[str, Tuple[str, str, float]] = {}
# trace_id -> (conversation_id, organization_id, monotonic_timestamp)

_PENDING_LINK_TTL = 120  # seconds


def register_pending_link(
    trace_id: str,
    conversation_id: str,
    organization_id: str,
) -> None:
    """Park a conversation link for deferred application.

    Called when ``crud.update_conversation_id_for_trace()`` returns 0
    because the SDK's spans have not been ingested yet.
    """
    with _lock:
        _pending[trace_id] = (
            conversation_id,
            organization_id,
            time.monotonic(),
        )
        # Evict stale entries while we hold the lock
        cutoff = time.monotonic() - _PENDING_LINK_TTL
        stale = [k for k, v in _pending.items() if v[2] < cutoff]
        for k in stale:
            del _pending[k]

    logger.debug(
        f"[CONVERSATION_LINKING] Parked pending link: "
        f"trace_id={trace_id}, conversation_id={conversation_id}"
    )


def apply_pending_links(
    db: Session,
    stored_spans: List[models.Trace],
) -> int:
    """Apply parked conversation links for recently stored spans.

    Called by the telemetry ingest endpoint after spans are committed.
    Returns the total number of span rows updated.
    """
    if not stored_spans:
        return 0

    unique_trace_ids = list({s.trace_id for s in stored_spans})

    # Pop matching entries under the lock, then apply outside it
    # to avoid holding the lock during DB operations.
    to_apply: List[Tuple[str, str, str]] = []
    with _lock:
        for tid in unique_trace_ids:
            entry = _pending.pop(tid, None)
            if entry:
                conv_id, org_id, _ = entry
                to_apply.append((tid, conv_id, org_id))

    if not to_apply:
        return 0

    total = 0
    for tid, conv_id, org_id in to_apply:
        count = crud.update_conversation_id_for_trace(db, tid, conv_id, org_id)
        total += count
        logger.info(
            f"[CONVERSATION_LINKING] Applied pending link: "
            f"trace_id={tid}, conversation_id={conv_id}, "
            f"updated={count} spans"
        )

    return total
