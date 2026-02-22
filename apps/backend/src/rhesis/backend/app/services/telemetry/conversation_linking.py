"""Deferred linking for conversation traces.

Two separate concerns are handled here, each with its own cache:

1. **Conversation ID linking** (first-turn only)
   Stateful endpoints generate a session/conversation ID in their
   response.  The first turn's trace is stored with
   ``conversation_id=NULL`` because the ID wasn't known yet.  After
   invocation, the backend discovers the ID and tries an immediate
   UPDATE.  If the SDK spans haven't arrived yet (async export), the
   mapping is parked and applied when the spans are ingested.

2. **Mapped output injection** (every SDK turn)
   The SDK tracer sets ``rhesis.conversation.input`` per-span, but
   cannot set ``rhesis.conversation.output`` because it only has the
   raw function return value — not the response-mapped output.  The
   backend parks the mapped output after invocation and injects it
   into the span's attributes *before* storage, when the SDK spans
   arrive at the telemetry ingest endpoint.

Both caches are process-level dicts protected by a shared lock.
Entries expire after ``_CACHE_TTL`` seconds.
"""

import logging
import threading
import time
from typing import Any, Dict, List, NamedTuple

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_CACHE_TTL = 120  # seconds


# ---------------------------------------------------------------
# 1. Conversation ID linking (first-turn patching)
# ---------------------------------------------------------------


class PendingConversationLink(NamedTuple):
    """A deferred conversation-id-to-trace mapping awaiting span arrival."""

    conversation_id: str
    organization_id: str
    registered_at: float  # time.monotonic() timestamp


_pending_conversation_links: Dict[str, PendingConversationLink] = {}


def register_pending_conversation_link(
    trace_id: str,
    conversation_id: str,
    organization_id: str,
) -> None:
    """Park a conversation-id link for deferred application.

    Called when ``crud.update_conversation_id_for_trace()`` returns 0
    because the SDK's spans have not been ingested yet.
    """
    with _lock:
        _pending_conversation_links[trace_id] = PendingConversationLink(
            conversation_id=conversation_id,
            organization_id=organization_id,
            registered_at=time.monotonic(),
        )
        _evict_stale(_pending_conversation_links)

    logger.debug(
        f"[CONVERSATION_LINKING] Parked pending link: "
        f"trace_id={trace_id}, conversation_id={conversation_id}"
    )


def apply_pending_conversation_links(
    db: Session,
    stored_spans: List[models.Trace],
) -> int:
    """Apply parked conversation-id links for recently stored spans.

    Called by the telemetry ingest endpoint after spans are committed.
    Returns the total number of span rows updated.

    RLS note: We switch the DB session's tenant context per-link so
    the UPDATE is visible through the RLS policy on the ``trace``
    table.
    """
    if not stored_spans:
        return 0

    unique_trace_ids = list({span.trace_id for span in stored_spans})

    matched: List[tuple[str, PendingConversationLink]] = []
    with _lock:
        for trace_id in unique_trace_ids:
            link = _pending_conversation_links.pop(trace_id, None)
            if link is not None:
                matched.append((trace_id, link))

    if not matched:
        return 0

    from rhesis.backend.app.database import set_session_variables

    total = 0
    for trace_id, link in matched:
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

    return total


# ---------------------------------------------------------------
# 2. Mapped output injection (per-turn, before span storage)
# ---------------------------------------------------------------


class PendingOutput(NamedTuple):
    """Mapped output waiting to be injected into an arriving SDK span."""

    mapped_output: str
    registered_at: float  # time.monotonic() timestamp


_pending_outputs: Dict[str, PendingOutput] = {}


def register_pending_output(
    trace_id: str,
    mapped_output: str,
) -> None:
    """Park a mapped output for injection when SDK spans arrive.

    Called by ``SdkEndpointInvoker.invoke()`` after response mapping.
    The SDK tracer already stamps ``rhesis.conversation.input`` on
    each root span — only the output needs to be added by the
    backend.
    """
    with _lock:
        _pending_outputs[trace_id] = PendingOutput(
            mapped_output=mapped_output,
            registered_at=time.monotonic(),
        )
        _evict_stale(_pending_outputs)

    logger.debug(f"[CONVERSATION_IO] Parked pending output for trace_id={trace_id}")


def inject_pending_output(
    spans: List[Any],
) -> int:
    """Inject parked mapped output into span attributes before storage.

    Called by the telemetry ingest endpoint *before*
    ``create_trace_spans()`` so the output is part of the span from
    the moment it is stored — no post-hoc UPDATE required.

    Only injects into root spans (no parent) that already carry
    ``rhesis.conversation.input`` but lack ``rhesis.conversation.output``.

    Args:
        spans: Mutable list of OTELSpan / OTELSpanCreate objects
               whose ``attributes`` dict will be mutated in place.

    Returns:
        Number of spans that received an output injection.
    """
    from rhesis.sdk.telemetry.constants import (
        ConversationContext as ConversationConstants,
    )

    input_key = ConversationConstants.SpanAttributes.CONVERSATION_INPUT
    output_key = ConversationConstants.SpanAttributes.CONVERSATION_OUTPUT

    # Collect unique trace_ids from the batch
    trace_ids = list({span.trace_id for span in spans})

    matched: Dict[str, PendingOutput] = {}
    with _lock:
        for trace_id in trace_ids:
            entry = _pending_outputs.pop(trace_id, None)
            if entry is not None:
                matched[trace_id] = entry

    if not matched:
        return 0

    injected_count = 0
    for span in spans:
        pending = matched.get(span.trace_id)
        if pending is None:
            continue

        # Only inject into root spans that have input but no output
        is_root = not span.parent_span_id
        has_input = input_key in span.attributes
        has_output = output_key in span.attributes

        if is_root and has_input and not has_output:
            span.attributes[output_key] = pending.mapped_output[:10000]
            injected_count += 1
            logger.debug(
                f"[CONVERSATION_IO] Injected output into span "
                f"{span.span_id} (trace {span.trace_id})"
            )

    return injected_count


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------


def _evict_stale(cache: dict) -> None:
    """Remove entries older than ``_CACHE_TTL`` (caller holds lock)."""
    cutoff = time.monotonic() - _CACHE_TTL
    stale_keys = [key for key, entry in cache.items() if entry.registered_at < cutoff]
    for key in stale_keys:
        del cache[key]
