"""Conversation-aware tracing for applications that drive Haystack from their own loop.

``auto_instrument("haystack")`` traces every pipeline run, but a chat application needs two more
things: turns grouped into one conversation rather than scattered across a trace per exchange, and
a span wrapping a whole run so a turn has a root of its own. Without that root, the Haystack
pipeline span claims the turn and reports the serialized pipeline input and output as the
conversation text.

This module imports Haystack only indirectly, through ``tracer.py``, and does so lazily.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Optional

from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, Span, SpanContext, TraceFlags

from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.context import get_root_trace_id, set_root_trace_id

if TYPE_CHECKING:
    from rhesis.sdk.telemetry.integrations.haystack.tracer import RhesisTracer

logger = logging.getLogger(__name__)

DEFAULT_TURN_SPAN_NAME = "function.haystack.turn"

_SPAN_ATTRS = ConversationContext.SpanAttributes
_MAX_IO = ConversationContext.MAX_IO_LENGTH

# Forwarded to RhesisClient when this class has to create one. Anything else a caller passes is a
# tracer setting, handled by HaystackIntegration.configure().
_CLIENT_KWARGS = ("api_key", "base_url", "project_id", "environment")


def _conversation_parent_context(trace_id: str) -> Any:
    """
    Build a synthetic parent so a turn inherits the conversation's trace id.

    OpenTelemetry mints a fresh trace id for every parentless span, which would scatter one
    conversation across a trace per turn. Attaching a non-recording parent carrying the
    conversation's trace id makes the new span join it instead. The parent's span id is the agreed
    placeholder that the Rhesis exporter strips, so the turn is still stored as a root span -- the
    same approach the Rhesis SDK uses for turns it serves itself.

    :param trace_id: 32-character hex trace id of the conversation's first turn.
    :returns: An OTel context carrying the synthetic parent, or ``None`` if the id is unusable.
    """
    try:
        span_context = SpanContext(
            trace_id=int(trace_id, 16),
            span_id=ConversationContext.SYNTHETIC_PARENT_SPAN_ID,
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
    except (TypeError, ValueError):
        logger.warning("Invalid conversation trace id %r; starting a new trace", trace_id)
        return None
    return trace.set_span_in_context(NonRecordingSpan(span_context))


class ConversationTurn:
    """
    A single conversation turn, yielded by :meth:`RhesisTracing.turn`.

    Assign :attr:`output` with the reply the user actually sees. Only the application knows what
    that is -- it may be a tool result or a value held in agent state rather than the last
    assistant message -- so it cannot be inferred from the span tree.
    """

    def __init__(self, span: Optional[Span] = None) -> None:
        self._span = span
        self._output = ""

    @property
    def span(self) -> Optional[Span]:
        """The underlying OTel span, or ``None`` when tracing is disabled."""
        return self._span

    @property
    def output(self) -> str:
        """The reply recorded for this turn."""
        return self._output

    @output.setter
    def output(self, reply: str) -> None:
        self._output = reply or ""
        if self._span is None or not self._output:
            return
        self._span.set_attribute(_SPAN_ATTRS.CONVERSATION_OUTPUT, self._output[:_MAX_IO])


class RhesisTracing:
    """
    Enable Rhesis tracing for an application that runs Haystack from its own loop.

    ``HAYSTACK_CONTENT_TRACING_ENABLED`` must be set to ``"true"`` before Haystack is imported,
    exactly as for ``auto_instrument("haystack")``.

    ### Usage example

    ```python
    import os

    os.environ["HAYSTACK_CONTENT_TRACING_ENABLED"] = "true"

    from rhesis.sdk.telemetry.integrations.haystack import RhesisTracing

    tracing = RhesisTracing("My Assistant")
    tracing.start_conversation("conversation-1")

    for message in ["Hello", "Tell me more"]:
        with tracing.turn(message) as turn:
            result = pipeline.run(...)
            turn.output = result["llm"]["replies"][0].text

    tracing.flush()
    ```
    """

    def __init__(
        self,
        name: str,
        *,
        enabled: bool = True,
        turn_span_name: str = DEFAULT_TURN_SPAN_NAME,
        **tracer_kwargs: Any,
    ) -> None:
        """
        Enable tracing, or fall back to a no-op when Rhesis is not configured.

        Construction never raises on a missing or rejected configuration: an application should run
        untraced rather than fail to start. Check :attr:`enabled` to report it.

        :param name: Trace name shown in the Rhesis UI.
        :param enabled: Set to ``False`` to build a no-op instance, so an application can gate
            tracing on its own policy without branching around every call.
        :param turn_span_name: Span name for each conversation turn root.
        :param tracer_kwargs: ``api_key``, ``base_url``, ``project_id`` and ``environment`` are used
            to create a ``RhesisClient`` when the process does not already have one;
            ``span_handler`` and ``frontend_url`` configure the tracer.
        """
        self.name = name
        self.turn_span_name = turn_span_name
        self._conversation_trace_id: Optional[str] = None
        self._tracer: Optional[RhesisTracer] = None

        if not enabled:
            logger.info("Rhesis tracing disabled by the caller.")
            return
        if not os.getenv("RHESIS_API_KEY") and "api_key" not in tracer_kwargs:
            logger.info("RHESIS_API_KEY is not set; Rhesis tracing is disabled.")
            return

        try:
            self._tracer = self._start_tracing(name, tracer_kwargs)
        except Exception as exc:  # noqa: BLE001 - tracing must never break the application
            logger.warning("Could not enable Rhesis tracing: %s", exc)

    @staticmethod
    def _start_tracing(name: str, tracer_kwargs: dict[str, Any]) -> Optional[RhesisTracer]:
        """Make sure a provider exists, then register the Haystack tracer against it."""
        from rhesis.sdk.decorators import get_default_client
        from rhesis.sdk.telemetry.integrations.haystack.integration import get_integration

        client_kwargs = {k: tracer_kwargs[k] for k in _CLIENT_KWARGS if k in tracer_kwargs}
        if get_default_client() is None:
            # Creating the client is what installs the OpenTelemetry provider the turn spans and
            # the Haystack spans are both opened through.
            from rhesis.sdk import RhesisClient

            RhesisClient(**client_kwargs)
        elif client_kwargs:
            logger.info(
                "A Rhesis client already exists, so %s were ignored; they only apply when "
                "RhesisTracing has to create the client itself.",
                ", ".join(sorted(client_kwargs)),
            )

        integration = get_integration()
        integration.configure(
            name=name,
            span_handler=tracer_kwargs.get("span_handler"),
            frontend_url=tracer_kwargs.get("frontend_url"),
        )
        if not integration.enable():
            logger.warning("Rhesis tracing could not be enabled for Haystack.")
            return None
        return integration.callback()

    @property
    def enabled(self) -> bool:
        """Whether tracing was successfully enabled."""
        return self._tracer is not None

    def start_conversation(self, conversation_id: str, **invocation_context: Any) -> None:
        """
        Group the turns that follow into one conversation, sharing one trace.

        Calling this again starts a new conversation: the next turn opens a new trace and later
        turns join it.

        :param conversation_id: Identifier grouping the turns, shown as the conversation in Rhesis.
        :param invocation_context: Extra metadata for the root span (test run identifiers, tags, …).
        """
        if not self.enabled:
            return
        from rhesis.sdk.telemetry.integrations.haystack.tracer import tracing_context_var

        tracing_context_var.set({"session_id": conversation_id, **invocation_context})
        self._conversation_trace_id = None

    @contextmanager
    def turn(self, user_input: str) -> Iterator[ConversationTurn]:
        """
        Open the root span for one conversation turn.

        Run the turn's work inside the block and assign the reply to
        :attr:`ConversationTurn.output`. Every turn after the first joins the first one's trace, so
        a conversation reads as one trace rather than one per exchange.

        Yields an inert turn when tracing is disabled, so callers need no branching.

        :param user_input: The user's message, recorded as the turn's conversation input.
        """
        tracer = self._tracer
        if tracer is None:
            yield ConversationTurn()
            return

        from rhesis.sdk.telemetry.integrations.haystack.tracer import tracing_context_var

        conversation_id = (tracing_context_var.get({}) or {}).get("session_id")
        parent_context = (
            _conversation_parent_context(self._conversation_trace_id)
            if self._conversation_trace_id
            else None
        )
        # Opened through the tracer's own provider rather than ``trace.get_tracer()`` so a turn is
        # flushed by the same provider as its children.
        otel_tracer = tracer.telemetry.otel_tracer
        previous_root = get_root_trace_id()

        with otel_tracer.start_as_current_span(self.turn_span_name, context=parent_context) as span:
            span.set_attribute(_SPAN_ATTRS.IS_TURN_ROOT, True)
            if conversation_id:
                span.set_attribute(_SPAN_ATTRS.CONVERSATION_ID, conversation_id)
            if user_input:
                span.set_attribute(_SPAN_ATTRS.CONVERSATION_INPUT, user_input[:_MAX_IO])

            trace_id = format(span.get_span_context().trace_id, "032x")
            self._conversation_trace_id = trace_id
            # Marks the turn as owned here, so the Haystack root span nests inside it instead of
            # claiming the turn and restating its input and output.
            set_root_trace_id(trace_id)
            try:
                yield ConversationTurn(span)
            finally:
                set_root_trace_id(previous_root)

    def flush(self) -> None:
        """Flush pending spans. Call before exit; batched spans are otherwise lost."""
        if self._tracer is not None:
            self._tracer.flush()


__all__ = ["DEFAULT_TURN_SPAN_NAME", "ConversationTurn", "RhesisTracing"]
