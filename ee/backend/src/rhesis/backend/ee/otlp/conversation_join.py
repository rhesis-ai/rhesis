"""Join conversation turns that arrive under separate trace ids.

Rhesis files a conversation as one trace id with one root span per turn; the
trace list, conversation view and evaluator all find a conversation's turns by
that id. The SDK makes this true on the client. An agent exporting the OTel GenAI
conventions starts a new trace per turn and links turns only through
``gen_ai.conversation.id``, so ingest re-files turns 2+ under the first turn's
trace id here, keeping the id they arrived with in
:data:`SOURCE_TRACE_ID_ATTRIBUTE`.

A turn's spans arrive over many requests, usually root last, and often only the
root carries the conversation id. So when it arrives, the spans of that turn
already stored are moved too, and the move is remembered for
:data:`ALIAS_TTL_SECONDS` so spans of the turn that arrive afterwards (exporter
retries, out-of-order batches) follow it.
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.constants import AISpanAttributes
from rhesis.backend.app.crud.telemetry import (
    first_root_start_time,
    get_trace_id_for_conversation,
    lock_ingest_buckets,
    lock_traces_for_ingest,
    move_spans_to_trace,
    update_conversation_id_for_trace,
)
from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase
from rhesis.telemetry.schemas import OTELSpan

logger = logging.getLogger(__name__)

SOURCE_TRACE_ID_ATTRIBUTE = AISpanAttributes.SOURCE_TRACE_ID

# The name OTLP ingest jobs use to ask the worker for this step.
PRE_STORE_HOOK = "otlp_conversation_join"

# Long enough to cover a turn's late spans: runs last up to an hour, and
# exporters retry for minutes after that.
ALIAS_TTL_SECONDS = 24 * 60 * 60

_PREFIX = "otlp:v1:trace-alias:"


class TraceAliasCache(RedisBackedCache):
    """source trace id -> conversation trace id, per org and project."""

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.CONVERSATION_LINKING,
            cache_name="otlp-trace-alias",
            ttl=ALIAS_TTL_SECONDS,
        )

    @staticmethod
    def _key(organization_id: str, project_id: str, trace_id: str) -> str:
        return f"{_PREFIX}{organization_id}:{project_id}:{trace_id}"

    def get(self, organization_id: str, project_id: str, trace_id: str) -> Optional[str]:
        self.initialize()
        return self._get(self._key(organization_id, project_id, trace_id))

    def set(self, organization_id: str, project_id: str, trace_id: str, target: str) -> None:
        self.initialize()
        self._set(self._key(organization_id, project_id, trace_id), target)


_aliases = TraceAliasCache()


def _refile(spans: List[OTELSpan], target_trace_id: str, conversation_id: Optional[str]) -> None:
    for span in spans:
        if span.trace_id != target_trace_id:
            span.attributes.setdefault(SOURCE_TRACE_ID_ATTRIBUTE, span.trace_id)
            span.trace_id = target_trace_id
        if conversation_id and not span.conversation_id:
            span.conversation_id = conversation_id


def _conversation_of(spans: List[OTELSpan]) -> Optional[str]:
    # Prefer the root's: a sub-agent can carry a conversation id of its own.
    roots = [s for s in spans if s.parent_span_id is None and s.conversation_id]
    if roots:
        return roots[0].conversation_id
    return next((s.conversation_id for s in spans if s.conversation_id), None)


_MAX_ALIAS_HOPS = 8


def _resolve(organization_id: str, project_id: str, trace_id: str) -> Optional[str]:
    """Where a turn's spans now live, following re-anchors (A -> B -> C)."""
    target = None
    current = trace_id
    for _ in range(_MAX_ALIAS_HOPS):
        nxt = _aliases.get(organization_id, project_id, current)
        if not nxt or nxt == current:
            break
        target = current = nxt
    return target


def _turn_start(spans: List[OTELSpan]) -> Optional[datetime]:
    roots = [s.start_time for s in spans if s.parent_span_id is None]
    return min(roots) if roots else None


def _follow(trace_id: str, moves: Dict[str, str]) -> str:
    seen = {trace_id}
    while trace_id in moves and moves[trace_id] not in seen:
        trace_id = moves[trace_id]
        seen.add(trace_id)
    return trace_id


def _join_turn(
    db: Session,
    trace_id: str,
    spans: List[OTELSpan],
    conversation_id: str,
    anchor: Optional[str],
    organization_id: str,
) -> tuple[str, Optional[tuple[str, str]]]:
    """File one turn under its conversation's trace.

    Returns the conversation's trace id afterwards, and the ``(source, target)``
    move made, if any. The conversation's trace is its earliest turn's: workers
    store turns in parallel, so a later turn can arrive first, and when the
    earlier one then arrives the conversation is moved onto it.
    """
    if not anchor or anchor == trace_id:
        # First turn: its id is the conversation's. Stamp the conversation on
        # the turn's spans that did not carry it, as the SDK does.
        _refile(spans, trace_id, conversation_id)
        update_conversation_id_for_trace(db, trace_id, conversation_id, organization_id)
        return trace_id, None

    incoming_start = _turn_start(spans)
    # None while the anchor is only in this batch; its turns are joined earliest first.
    anchor_start = first_root_start_time(db, anchor)
    if incoming_start and anchor_start and incoming_start < anchor_start:
        source, target = anchor, trace_id
        _refile(spans, trace_id, conversation_id)
        update_conversation_id_for_trace(db, trace_id, conversation_id, organization_id)
    else:
        source, target = trace_id, anchor
        _refile(spans, anchor, conversation_id)

    moved = move_spans_to_trace(db, source, target, conversation_id, SOURCE_TRACE_ID_ATTRIBUTE)
    logger.info(
        "Joined conversation turn trace_id=%s onto trace_id=%s (moved %d stored spans)",
        source,
        target,
        moved,
    )
    return target, (source, target)


def _settle_aliases(
    db: Session, organization_id: str, project_id: str, trace_ids: Iterable[str]
) -> Dict[str, str]:
    """Each trace's alias target, with that target locked.

    A job holding a trace's lock may move it, so an alias read before the lock
    can be stale; read again until the targets stop changing.
    """
    aliases: Dict[str, str] = {}
    for _ in range(_MAX_ALIAS_HOPS):
        current = {}
        for trace_id in trace_ids:
            target = _resolve(organization_id, project_id, trace_id)
            if target:
                current[trace_id] = target
        new_targets = set(current.values()) - set(aliases.values())
        aliases = current
        if not new_targets:
            break
        lock_traces_for_ingest(db, organization_id, new_targets)
    return aliases


def _turns_in_order(
    by_trace: Dict[str, List[OTELSpan]], conversations: Dict[str, str]
) -> Dict[str, List[str]]:
    """conversation id -> this batch's turns of it, earliest first (no root last)."""
    turns: Dict[str, List[str]] = defaultdict(list)
    for trace_id, conversation_id in conversations.items():
        turns[conversation_id].append(trace_id)

    def order(trace_id: str) -> tuple:
        start = _turn_start(by_trace[trace_id])
        return (start is None, start or datetime.min, trace_id)

    return {conversation_id: sorted(ids, key=order) for conversation_id, ids in turns.items()}


def join_conversation_turns(
    db: Session,
    spans: List[OTELSpan],
    organization_id: str,
    project_id: str,
) -> int:
    """Re-file this batch's turns onto their conversation's trace. Returns turns joined.

    ``db`` must be bound to the project. Mutates ``spans`` in place and moves
    spans of those turns already stored. Takes every lock it needs in a fixed
    order (conversations, then traces in one sorted pass), so jobs do not deadlock.
    """
    by_trace: Dict[str, List[OTELSpan]] = defaultdict(list)
    for span in spans:
        by_trace[span.trace_id].append(span)

    aliases = {t: a for t in by_trace if (a := _resolve(organization_id, project_id, t))}
    conversations = {
        trace_id: conversation_id
        for trace_id, trace_spans in by_trace.items()
        if trace_id not in aliases and (conversation_id := _conversation_of(trace_spans))
    }
    # Serializes joins per conversation, so two turns stored at once cannot both
    # find no anchor and split the conversation.
    lock_ingest_buckets(
        db, f"otlp-conversation:{organization_id}:{project_id}", conversations.values()
    )
    anchors = {
        conversation_id: get_trace_id_for_conversation(
            db, conversation_id, project_id, organization_id
        )
        for conversation_id in set(conversations.values())
    }
    lock_traces_for_ingest(
        db, organization_id, [*by_trace, *aliases.values(), *filter(None, anchors.values())]
    )
    aliases = _settle_aliases(db, organization_id, project_id, by_trace)

    moves: Dict[str, str] = dict(aliases)
    joined = 0
    for conversation_id, turn_ids in _turns_in_order(by_trace, conversations).items():
        anchor = anchors[conversation_id]
        for trace_id in turn_ids:
            if trace_id in aliases:
                continue
            anchor, move = _join_turn(
                db, trace_id, by_trace[trace_id], conversation_id, anchor, organization_id
            )
            if move:
                source, target = move
                moves[source] = target
                # Written before commit, while the traces are locked, so a job
                # waiting on them reads it. If this transaction rolls back, the
                # next batch of that trace finishes the move (below).
                _aliases.set(organization_id, project_id, source, target)
                joined += 1

    for source, target in aliases.items():
        # Spans of the turn stored before the alias was written follow it too.
        move_spans_to_trace(db, source, target, None, SOURCE_TRACE_ID_ATTRIBUTE)
    for trace_id, trace_spans in by_trace.items():
        target = _follow(trace_id, moves)
        if target != trace_id:
            _refile(trace_spans, target, None)
    return joined
