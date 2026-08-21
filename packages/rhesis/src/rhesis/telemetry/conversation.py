"""Conversation turns for apps that own their own turn boundary.

A framework integration can group a multi-turn session on its own, but it can only
report a reply it can *see*. Natively instrumented frameworks put the model's text
on their model spans, so an app whose reply is the model's last message needs
nothing from this module.

An app that composes its reply elsewhere — from a tool result, from a template,
from its own branching — is a different case. That text exists in no span, and the
framework's run root has already ended by the time the app holds it, so neither a
ContextVar nor a later call can attach it. Something has to own a span that
outlives the run:

    with conversation_turn(conversation_id, input=message) as turn:
        result = run_my_agent(message)
        turn.output = result["reply"]

That span becomes the turn root, carries the input and the reply, and joins the
conversation's turns into one trace. Nothing else in the app changes.

Behind ``@endpoint`` or ``@observe``, or in any platform-driven turn, Rhesis
already owns the turn root and publishes its trace id onwards. This stands down
there: it binds the conversation id and opens no span, because two spans claiming
``is_turn_root`` in one exchange makes the exporter strip the real parent of one of
them and the subtree detaches into a phantom turn.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Lock
from typing import Iterator, Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.context import (
    get_conversation_id,
    get_conversation_trace_id,
    get_root_trace_id,
    is_tracing_disabled,
    set_conversation_id,
    set_conversation_trace_id,
    set_root_trace_id,
)

logger = logging.getLogger(__name__)

DEFAULT_TURN_SPAN_NAME = "function.conversation_turn"

_TRACER_NAME = "rhesis.telemetry.conversation"


def build_conversation_parent_context(conv_trace_id: str) -> Optional[trace.Context]:
    """Build a synthetic OTEL parent so a new span inherits ``conv_trace_id``.

    A trace id is assigned when a span is created and cannot be changed afterwards,
    so the only way to put this turn on the conversation's trace is to give it a
    parent that already lives there. The parent is a non-recording placeholder with
    a reserved span id that
    :class:`~rhesis.telemetry.exporter.RhesisOTLPExporter` strips on export, so the
    turn is still stored as a root span.

    Args:
        conv_trace_id: 32-char hex trace id of the conversation.

    Returns:
        A context carrying the synthetic parent, or ``None`` if the id is unusable.
    """
    try:
        trace_id_int = int(conv_trace_id, 16)
    except (TypeError, ValueError):
        logger.warning("Invalid conversation trace_id: %s", conv_trace_id)
        return None
    if not trace_id_int:
        logger.warning("Invalid conversation trace_id: %s", conv_trace_id)
        return None
    synthetic_parent = NonRecordingSpan(
        SpanContext(
            trace_id=trace_id_int,
            span_id=ConversationContext.SYNTHETIC_PARENT_SPAN_ID,
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
    )
    return trace.set_span_in_context(synthetic_parent)


class _ConversationAnchors:
    """Remembers which trace each conversation started on.

    The first turn keeps the trace id it was born with; later turns are pulled onto
    it. Anything that observed or published an id for the first turn therefore still
    resolves. Bounded, so a long-lived process does not accumulate an entry per
    conversation forever.
    """

    def __init__(self, *, max_conversations: int = 2048) -> None:
        self._anchors: dict[str, str] = {}
        self._lock = Lock()
        self._max_conversations = max_conversations

    def get(self, conversation_id: str) -> Optional[str]:
        return self._anchors.get(conversation_id)

    def set(self, conversation_id: str, trace_id: str) -> None:
        with self._lock:
            while len(self._anchors) >= self._max_conversations:
                try:
                    self._anchors.pop(next(iter(self._anchors)))
                except StopIteration:  # pragma: no cover - racy but harmless
                    break
            self._anchors.setdefault(conversation_id, trace_id)

    def clear(self) -> None:
        with self._lock:
            self._anchors.clear()


_anchors = _ConversationAnchors()


class ConversationTurn:
    """Handle for one turn. Set :attr:`output` to record the reply.

    Yielded whether or not a span was opened, so app code never has to branch on
    whether tracing is configured.
    """

    __slots__ = ("_span", "conversation_id", "input", "output")

    def __init__(self, conversation_id: str, span, input: Optional[str] = None) -> None:
        self.conversation_id = conversation_id
        self.input = input
        self.output: Optional[str] = None
        self._span = span

    @property
    def trace_id(self) -> Optional[str]:
        """Hex trace id this turn was recorded on, or ``None`` if untraced."""
        if self._span is None:
            return None
        context = self._span.get_span_context()
        if context is None or not context.is_valid:
            return None
        return format(context.trace_id, "032x")

    def _stamp_output(self) -> None:
        if self._span is None or not self.output:
            return
        self._span.set_attribute(
            ConversationContext.SpanAttributes.CONVERSATION_OUTPUT,
            str(self.output)[: ConversationContext.MAX_IO_LENGTH],
        )


@contextmanager
def conversation_turn(
    conversation_id: str,
    *,
    input: Optional[str] = None,
    name: str = DEFAULT_TURN_SPAN_NAME,
) -> Iterator[ConversationTurn]:
    """Own one conversation turn: bind the id, and record its input and reply.

    Args:
        conversation_id: Groups this turn with the others in its conversation.
        input: The user's message. Stamped on entry.
        name: Turn-root span name. Must be ``function.*`` or a valid ``ai.*``
            operation, or the backend rejects the span; the default is safe.

    Yields:
        A :class:`ConversationTurn`. Assign ``turn.output`` before the block ends —
        that is the whole point of the span outliving the agent run.

    Opens no span, and only binds the conversation id, when tracing is off, when no
    recording tracer provider is installed, or when Rhesis already owns this turn's
    trace -- behind ``@endpoint`` / ``@observe``, or in any platform-driven turn
    that supplied a conversation trace id.
    """
    previous_conversation_id = get_conversation_id()
    previous_conversation_trace_id = get_conversation_trace_id()
    set_conversation_id(conversation_id)

    # Either ContextVar means Rhesis already owns this turn's trace and reports it
    # onwards -- ``root_trace_id`` from an enclosing @endpoint / @observe span,
    # ``conversation_trace_id`` from a platform-driven turn whose own record is
    # written to that trace. A second span claiming the turn root would fight it.
    owned_elsewhere = (
        is_tracing_disabled()
        or get_root_trace_id() is not None
        or previous_conversation_trace_id is not None
    )
    # Only an SDK TracerProvider records: the default global is a no-op proxy that
    # still answers get_tracer() but hands back an invalid, all-zero trace id,
    # which would then be published as this conversation's anchor.
    provider = None if owned_elsewhere else trace.get_tracer_provider()
    if owned_elsewhere or not isinstance(provider, SDKTracerProvider):
        try:
            yield ConversationTurn(conversation_id, None, input)
        finally:
            set_conversation_id(previous_conversation_id)
        return

    anchor = _anchors.get(conversation_id)
    parent_context = build_conversation_parent_context(anchor) if anchor else None

    attributes = ConversationContext.SpanAttributes
    tracer = provider.get_tracer(_TRACER_NAME)
    turn: Optional[ConversationTurn] = None
    try:
        with tracer.start_as_current_span(name, context=parent_context) as span:
            span_context = span.get_span_context()
            # A provider that has been shut down hands back a non-recording span.
            # Anchoring the conversation to its all-zero trace id would send every
            # later turn to a trace that cannot exist.
            trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else None
            if trace_id:
                # First turn of the conversation: its own trace becomes the anchor,
                # published so nested integrations join it rather than invent one.
                _anchors.set(conversation_id, trace_id)
                set_root_trace_id(trace_id)
                set_conversation_trace_id(trace_id)

            span.set_attribute(attributes.IS_TURN_ROOT, True)
            span.set_attribute(attributes.CONVERSATION_ID, conversation_id)
            if input:
                span.set_attribute(
                    attributes.CONVERSATION_INPUT,
                    str(input)[: ConversationContext.MAX_IO_LENGTH],
                )

            turn = ConversationTurn(conversation_id, span, input)
            try:
                yield turn
            finally:
                # Inside the span: the reply has to land before it ends.
                turn._stamp_output()
    finally:
        set_conversation_id(previous_conversation_id)
        set_conversation_trace_id(previous_conversation_trace_id)
        set_root_trace_id(None)


__all__ = [
    "DEFAULT_TURN_SPAN_NAME",
    "ConversationTurn",
    "build_conversation_parent_context",
    "conversation_turn",
]
