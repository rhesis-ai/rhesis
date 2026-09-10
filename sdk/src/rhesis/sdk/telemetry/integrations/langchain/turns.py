"""Deciding when a LangGraph run opens a conversation turn.

The exporter gives every span sharing a trace the conversation id published by
that trace's turn root, so a turn root is what makes multi-turn traces hang
together. Exactly one span per exchange may claim it: two claiming spans make
the exporter strip the real parent of one of them, detaching its subtree into a
phantom turn.
"""

from typing import Any, Dict, NamedTuple, Optional

from opentelemetry import trace

from rhesis.sdk.telemetry.integrations.langchain.extractors import (
    extract_conversation_id,
    is_langgraph_root,
)
from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.context import get_conversation_trace_id, get_root_trace_id
from rhesis.telemetry.conversation import (
    anchor_conversation,
    build_conversation_parent_context,
    get_conversation_anchor,
)

_ATTRS = ConversationContext.SpanAttributes


class TurnClaim(NamedTuple):
    """A run that opens a conversation turn, and the trace to open it on."""

    conversation_id: str
    parent_context: Any
    """Synthetic parent onto an earlier turn's trace, or None for the first turn."""


def resolve_turn(parent_run_id: Any, metadata: Optional[Dict]) -> Optional[TurnClaim]:
    """Decide whether this run opens a conversation turn, and on which trace.

    Only a LangGraph root qualifies, and only when nothing else already owns
    the turn: an enclosing ``conversation_turn``, ``@endpoint`` or ``@observe``
    stands this down, as does any ambient span the run would nest under.
    """
    if parent_run_id or not is_langgraph_root(metadata):
        return None

    if get_root_trace_id() is not None or get_conversation_trace_id() is not None:
        return None

    if trace.get_current_span().get_span_context().is_valid:
        return None

    conversation_id = extract_conversation_id(metadata)
    if not conversation_id:
        return None

    anchor = get_conversation_anchor(conversation_id)
    parent_context = build_conversation_parent_context(anchor) if anchor else None
    return TurnClaim(conversation_id, parent_context)


def claim_turn_root(span: trace.Span, claim: TurnClaim) -> None:
    """Mark a span as the root of a conversation turn.

    The exporter reads these two attributes to give every span sharing this
    trace the same conversation id.
    """
    span.set_attribute(_ATTRS.IS_TURN_ROOT, True)
    span.set_attribute(_ATTRS.CONVERSATION_ID, claim.conversation_id)

    span_context = span.get_span_context()
    if span_context.is_valid:
        # First turn of this conversation anchors it; later turns were already
        # pulled onto that trace by the parent context above.
        anchor_conversation(claim.conversation_id, format(span_context.trace_id, "032x"))
