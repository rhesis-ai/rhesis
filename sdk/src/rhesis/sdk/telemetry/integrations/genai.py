"""Shared helpers for integrations built on native GenAI OTel instrumentation.

Frameworks like Microsoft Agent Framework and Pydantic AI emit OpenTelemetry
spans natively following the GenAI semantic conventions (``gen_ai.*``
attributes, ``chat`` / ``invoke_agent`` / ``execute_tool`` operations). The
Rhesis backend expects the ``ai.*`` / ``function.*`` schema instead.

The pure, framework-neutral mapping (attribute names, operation values,
attribute and event translation, message-event synthesis) lives in
:mod:`rhesis.telemetry.genai`, which the backend's OTLP ingest uses too. It is
re-exported here so integrations keep importing from one place. This module adds
what needs the OpenTelemetry SDK:

- :class:`TranslatedSpan` / :class:`RetracedSpan`, read-only ``ReadableSpan`` views,
- conversation, ancestry and release registries used at export time,
- helpers to swap the exporter under an existing span processor, and
- the shared content-capture opt-out env var.

Framework-specific logic (span-name maps, workflow spans, handoff heuristics)
stays in each integration's own ``mapping.py`` / ``translator.py``.
"""

from __future__ import annotations

import logging
import os
from threading import Lock
from typing import Any, Iterable, Mapping, Optional, Sequence

from opentelemetry.sdk.trace import Event, ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.trace import SpanContext

from rhesis.telemetry.conversation import anchor_conversation, get_conversation_anchor
from rhesis.telemetry.genai import (  # noqa: F401 - re-exported for integrations
    EVENT_ASSISTANT_MESSAGE,
    EVENT_CHOICE,
    EVENT_SYSTEM_MESSAGE,
    EVENT_TOOL_MESSAGE,
    EVENT_USER_MESSAGE,
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_AGENT_ID,
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OPERATION_NAME,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_RESPONSE_FINISH_REASONS,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_SYSTEM_INSTRUCTIONS,
    GEN_AI_TOOL_CALL_ARGS,
    GEN_AI_TOOL_CALL_RESULT,
    GEN_AI_TOOL_DESCRIPTION,
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_TYPE,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    OP_CHAT,
    OP_CREATE_AGENT,
    OP_EMBEDDINGS,
    OP_EXECUTE_TOOL,
    OP_INVOKE_AGENT,
    OPERATION_TO_AI_TYPE,
    coerce_message_list,
    extract_conversation_input,
    extract_conversation_output,
    join_message_parts,
    join_text_parts,
    synthesize_message_events,
    synthesize_tool_io_events,
    to_json_text,
    translate_attributes,
    translate_event_attributes,
    translate_event_name,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TranslatedSpan: read-only ReadableSpan view with swapped name/attrs/events
# ---------------------------------------------------------------------------

# Sentinel for ``TranslatedSpan(new_parent=...)``. A plain ``None`` default
# would be ambiguous: ``None`` is also a legitimate parent value meaning "this
# span is a trace root", so we need a third value for "leave the parent alone".
KEEP_PARENT = object()


class TranslatedSpan(ReadableSpan):
    """Read-only view that swaps the original span's name/attributes/events.

    OTEL ``ReadableSpan`` exposes its data via properties. By overriding only
    the four we care about we get a span that quacks like the original (kind,
    status, timestamps, resource, instrumentation_scope, ...) but that appears
    in the Rhesis ``ai.*`` namespace to downstream consumers.

    ``new_parent`` is optional and defaults to :data:`KEEP_PARENT`; pass a
    ``SpanContext`` (or ``None``) only to re-point a span whose real parent the
    integration dropped.
    """

    def __init__(
        self,
        original: ReadableSpan,
        new_name: str,
        new_attributes: Mapping[str, Any],
        new_events: Sequence[Event],
        new_parent: Any = KEEP_PARENT,
    ) -> None:
        # Skip ReadableSpan.__init__ on purpose: the parent stores fields in
        # private slots and forces us to copy them all over. Instead, we keep
        # the underlying span and forward unknown attribute access via
        # ``__getattr__`` below.
        self._original = original
        self._new_name = new_name
        self._new_attributes = dict(new_attributes)
        self._new_events = tuple(new_events)
        self._new_parent = new_parent

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._new_name

    @property
    def attributes(self):  # type: ignore[override]
        return self._new_attributes

    @property
    def events(self):  # type: ignore[override]
        return self._new_events

    @property
    def parent(self):  # type: ignore[override]
        # Lets an integration re-point a span whose real parent it dropped, so
        # the child does not orphan in the exported trace.
        if self._new_parent is KEEP_PARENT:
            return self._original.parent
        return self._new_parent

    def __getattr__(self, item: str) -> Any:
        # __getattr__ is only consulted when normal lookup fails, so it never
        # masks the explicit overrides above.
        return getattr(self._original, item)

    def to_json(self, indent: int = 4) -> str:  # type: ignore[override]
        return self._original.to_json(indent=indent)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"TranslatedSpan(name={self._new_name!r}, original={self._original!r})"


class RetracedSpan(ReadableSpan):
    """Read-only view that moves a span onto a different trace id.

    Composes over anything ``ReadableSpan``-shaped, :class:`TranslatedSpan`
    included, which is why every public property is forwarded by hand instead of
    leaning on ``__getattr__``. ``ReadableSpan`` implements them as properties
    over private slots this wrapper never sets, so an inherited ``attributes``
    would resolve ``self._attributes`` through ``__getattr__`` onto the
    *innermost* span and quietly hand back the untranslated values.

    The parent link is rebound to the new trace as well: only ``span_id`` reaches
    the Rhesis exporter, but a parent context still pointing at the abandoned
    trace is an inconsistency the next reader has to work out.
    """

    def __init__(self, original: ReadableSpan, trace_id: int) -> None:
        # Same reason as TranslatedSpan for skipping ReadableSpan.__init__.
        self._original = original
        self._context = self._rebind(original.context, trace_id)
        self._parent = self._rebind(original.parent, trace_id)

    @staticmethod
    def _rebind(ctx: Optional[SpanContext], trace_id: int) -> Optional[SpanContext]:
        if ctx is None:
            return None
        return SpanContext(
            trace_id=trace_id,
            span_id=ctx.span_id,
            is_remote=ctx.is_remote,
            trace_flags=ctx.trace_flags,
            trace_state=ctx.trace_state,
        )

    @property
    def context(self):  # type: ignore[override]
        return self._context

    @property
    def parent(self):  # type: ignore[override]
        return self._parent

    def get_span_context(self):  # type: ignore[override]
        return self._context

    @property
    def name(self):  # type: ignore[override]
        return self._original.name

    @property
    def attributes(self):  # type: ignore[override]
        return self._original.attributes

    @property
    def events(self):  # type: ignore[override]
        return self._original.events

    @property
    def links(self):  # type: ignore[override]
        return self._original.links

    @property
    def kind(self):  # type: ignore[override]
        return self._original.kind

    @property
    def status(self):  # type: ignore[override]
        return self._original.status

    @property
    def start_time(self):  # type: ignore[override]
        return self._original.start_time

    @property
    def end_time(self):  # type: ignore[override]
        return self._original.end_time

    @property
    def resource(self):  # type: ignore[override]
        return self._original.resource

    @property
    def instrumentation_scope(self):  # type: ignore[override]
        return self._original.instrumentation_scope

    @property
    def instrumentation_info(self):  # type: ignore[override]
        return self._original.instrumentation_info

    @property
    def dropped_attributes(self):  # type: ignore[override]
        return self._original.dropped_attributes

    @property
    def dropped_events(self):  # type: ignore[override]
        return self._original.dropped_events

    @property
    def dropped_links(self):  # type: ignore[override]
        return self._original.dropped_links

    def to_json(self, indent: int = 4) -> str:  # type: ignore[override]
        return self._original.to_json(indent=indent)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._original, item)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        trace_id = format(self._context.trace_id, "032x") if self._context else None
        return f"RetracedSpan(trace_id={trace_id}, original={self._original!r})"


class ConversationTraceRegistry:
    """Joins the traces of one conversation onto the trace id of its first turn.

    A natively instrumented framework opens its own root span per turn, so OTEL
    mints a fresh trace id each time and a conversation arrives as one unrelated
    trace per turn. This records the first turn's id and hands it back for the
    rest, so later turns can be rewritten onto it.

    Which trace a conversation is anchored to is **not** decided here. It is read
    from and written to the process-wide store in
    :mod:`rhesis.telemetry.conversation`, the same one ``conversation_turn``,
    ``@endpoint``/``@observe``, LangGraph and Haystack use. Keeping a second
    store here meant the two disagreed for the same conversation id: a turn
    opened by ``conversation_turn`` and a later bare framework run under the same
    id each anchored their own trace, and the conversation arrived as two.

    Two rules keep that from corrupting anything. The first turn is **never**
    rewritten -- it keeps the id it was born with, which is the id anything else
    in the process would have observed and published. And the caller must not
    claim at all when something outside the process owns the trace identity; see
    the ``root_trace_id`` / ``conversation_trace_id`` check at the call site. An
    id we invented can never match one a backend minted independently, and a span
    written to a trace id nobody else knows is a span nothing can link to.

    Written at span *start*, where the conversation ContextVars are still live,
    and read at *export*, where they are not -- a ``BatchSpanProcessor`` exports
    on its own thread. :meth:`claim` therefore has to run on the first span of a
    trace, which is the framework's run root: it starts before every span whose
    trace id will need rewriting, so no span can escape with the wrong id.

    The rewrite map is bounded, because a long-lived process would otherwise
    keep one entry per trace forever. The anchors are bounded by the shared
    store.
    """

    def __init__(self, *, max_traces: int = 4096) -> None:
        self._targets: dict[int, int] = {}
        self._lock = Lock()
        self._max_traces = max_traces

    def claim(self, trace_id: Optional[int], conversation_id: Optional[str]) -> None:
        """Anchor ``conversation_id`` to a trace, once per trace.

        The first turn seen for a conversation becomes its anchor and is left
        alone. Every later turn records a rewrite onto that anchor.

        The anchor is written before it is read back, so the shared store's
        first-writer-wins is the single decision about who anchors a
        conversation. Two threads opening the same conversation at once both
        write; whichever the store keeps is the anchor, and the other reads it
        back and records a rewrite onto it like any later turn.
        """
        # ``not trace_id`` rejects OTEL's all-zero invalid id as well as None. A
        # non-recording span carries that id, and writing it as an anchor would
        # poison the conversation for the life of the process: the store keeps
        # the first value written, so no healthy later turn could correct it.
        if not trace_id or not conversation_id or trace_id in self._targets:
            return

        own_id = format(trace_id, "032x")
        anchor_conversation(conversation_id, own_id)
        anchor_id = get_conversation_anchor(conversation_id)
        if anchor_id is None or anchor_id == own_id:
            # This turn anchors the conversation, so it is never rewritten.
            return
        try:
            anchor = int(anchor_id, 16)
        except (TypeError, ValueError):  # pragma: no cover - the store holds hex
            logger.debug("Unusable conversation anchor %r", anchor_id)
            return
        if not anchor or anchor == trace_id:
            return

        with self._lock:
            self._evict(self._targets, self._max_traces)
            self._targets.setdefault(trace_id, anchor)

    @staticmethod
    def _evict(store: dict, limit: int) -> None:
        while len(store) >= limit:
            try:
                store.pop(next(iter(store)))
            except StopIteration:  # pragma: no cover - racy but harmless
                return

    def target(self, trace_id: Optional[int]) -> Optional[int]:
        """Return the trace id to rewrite to, or ``None`` to leave the span alone."""
        if trace_id is None:
            return None
        target = self._targets.get(trace_id)
        if target is None or target == trace_id:
            return None
        return target

    def clear(self) -> None:
        """Forget the rewrites. The shared anchor store is not this class's to clear."""
        with self._lock:
            self._targets.clear()


class DeferredReleaseQueue:
    """Frees per-trace entries a bounded number of reads after the first read.

    A natively instrumented framework carries a turn's text on its nested model
    spans, not on the run root that has to be stamped with it, so an integration
    collects that text per trace id and reads it back when the root is exported.
    Popping it on that read looks right and is not: ``enable()`` wraps *every*
    exporter on the provider, so a process running its own OTLP collector beside
    Rhesis exports the same spans through several translating exporters, and
    whichever reached the root first took the content and left the others
    stamping a root span with nothing on it.

    Keeping every entry instead trades that for a leak: at
    :data:`~rhesis.telemetry.constants.ConversationContext.MAX_IO_LENGTH` per
    field, a long-running process would sit on megabytes of conversation text
    waiting for the store's own entry cap. So entries are freed once enough
    other traces have been read past them - long enough for the other exporters
    to see the same trace, short enough to stay small. The queue is deliberately
    larger than an OTEL export batch, since a busy service can flush hundreds of
    run roots at once and the exporters do not drain their queues in lockstep.

    Holds the stores by reference and mutates them in place, so an owner must
    not rebind them after construction. Takes no lock of its own: every method
    expects the owner's lock to be held, which is what keeps a read of the
    stores and the release that follows it atomic together.
    """

    def __init__(self, *stores: dict, max_served: int = 512) -> None:
        """Queue releases across ``stores``, all keyed by trace id."""
        self._stores = stores
        self._served: dict[int, None] = {}
        self._max_served = max_served

    def queue_release(self, trace_id: int) -> None:
        """Mark ``trace_id`` read, freeing whatever has fallen far enough behind.

        A trace with nothing recorded takes no slot: it has nothing to free, and
        a run of content-free traces would otherwise push out the entries of the
        traces that do have some. Caller holds the lock.
        """
        if not self.has_entries(trace_id):
            return
        # Re-reading moves a trace back to the newest, so the entries stay while
        # anything is still asking for them.
        self._served.pop(trace_id, None)
        self._served[trace_id] = None
        while len(self._served) > self._max_served:
            stale = next(iter(self._served))
            del self._served[stale]
            for store in self._stores:
                store.pop(stale, None)

    def has_entries(self, trace_id: int) -> bool:
        """Whether any store holds something for this trace. Caller holds the lock.

        Every store an owner keeps has to be passed in. One left out is invisible
        here, so its entries never reach the queue and never get freed - which is
        the leak this class exists to prevent.
        """
        return any(trace_id in store for store in self._stores)

    def clear(self) -> None:
        """Forget the queue and empty every store. Caller holds the lock."""
        self._served.clear()
        for store in self._stores:
            store.clear()


def translate_events(
    original_events: Iterable[Event],
    span_attributes: Mapping[str, Any],
) -> list[Event]:
    """Build the new event list, including synthesized message/tool I/O events."""
    new_events: list[Event] = []
    for event in original_events:
        new_name = translate_event_name(event.name)
        new_attrs = translate_event_attributes(event.name, event.attributes or {})
        new_events.append(Event(name=new_name, attributes=new_attrs, timestamp=event.timestamp))

    for synth_name, synth_attrs in synthesize_message_events(span_attributes):
        new_events.append(Event(name=synth_name, attributes=synth_attrs))

    for synth_name, synth_attrs in synthesize_tool_io_events(span_attributes):
        new_events.append(Event(name=synth_name, attributes=synth_attrs))

    return new_events


# ---------------------------------------------------------------------------
# Span ancestry registry for handoff from-agent resolution
# ---------------------------------------------------------------------------


class AncestryRegistry:
    """Persistent (process-lifetime) span ancestry index for handoff edges.

    A batch-local parent walk fails when a delegated/handed-off span and its
    enclosing agent spans are exported in different batches. That is the
    common case under ``BatchSpanProcessor``: a child span ends (and is
    enqueued) *before* its parent, so on long runs the agent ancestor lands in
    a later batch than the span that needs it.

    This registry sidesteps batching entirely by recording ancestry at span
    *start* time (a parent always starts before its children, and both MAF and
    Pydantic AI embed the agent name in the ``invoke_agent <name>`` span name
    from the start). The exporter then resolves the calling agent against this
    index regardless of which batch each span exports in.

    ``track_siblings`` covers MAF's ``HandoffBuilder`` layout, where the
    ``invoke_agent`` span and the ``chat`` span are SIBLINGS sharing the same
    ``executor.process`` parent, so the plain parent-chain walk can't see the
    agent. It must stay **off** for frameworks with properly nested delegation
    (like Pydantic AI, where the chain is ``invoke_agent (child) ->
    execute_tool -> invoke_agent (parent)``): with siblings on, a delegated
    agent span would resolve *itself* through its own parent entry and report
    its own name as the calling agent.

    All stores are bounded; the oldest entries are evicted once the cap is hit.
    """

    def __init__(
        self,
        *,
        agent_name_prefix: str = "invoke_agent ",
        track_siblings: bool = False,
        max_entries: int = 8192,
    ) -> None:
        self._agent_name_prefix = agent_name_prefix
        self._track_siblings = track_siblings
        self._parent_by_span_id: dict[int, int] = {}
        self._agent_by_span_id: dict[int, str] = {}
        # Agent name indexed by its *parent* span id (sibling layout, see
        # class docstring). Only populated when ``track_siblings`` is on.
        self._agent_by_parent_span_id: dict[int, str] = {}
        self._max_entries = max_entries

    @staticmethod
    def _span_id(span: Any) -> int | None:
        ctx = getattr(span, "context", None)
        if ctx is None:
            try:
                ctx = span.get_span_context()
            except Exception:  # noqa: BLE001
                return None
        return getattr(ctx, "span_id", None)

    def _evict_if_needed(self, store: dict[int, Any]) -> None:
        if len(store) < self._max_entries:
            return
        try:
            first = next(iter(store))
            store.pop(first, None)
        except StopIteration:  # pragma: no cover - racy but harmless
            pass

    def record(self, span: Any) -> None:
        """Index a span's parent link and (if an agent span) its name.

        Safe to call from a span processor's ``on_start``; never raises.
        """
        try:
            span_id = self._span_id(span)
            if span_id is None:
                return
            parent_ctx = getattr(span, "parent", None)
            parent_sid = getattr(parent_ctx, "span_id", None)
            if parent_sid is not None:
                self._evict_if_needed(self._parent_by_span_id)
                self._parent_by_span_id[span_id] = parent_sid
            name = getattr(span, "name", "") or ""
            if name.startswith(self._agent_name_prefix):
                agent_name = name[len(self._agent_name_prefix) :].strip()
                if agent_name:
                    self._evict_if_needed(self._agent_by_span_id)
                    self._agent_by_span_id[span_id] = agent_name
                    if self._track_siblings and parent_sid is not None:
                        self._evict_if_needed(self._agent_by_parent_span_id)
                        self._agent_by_parent_span_id[parent_sid] = agent_name
        except Exception:  # noqa: BLE001 - recording must never break tracing
            logger.debug("Failed to record span ancestry", exc_info=True)

    def find_ancestor_agent(self, span: Any) -> str | None:
        """Resolve the calling agent for a delegated/handoff span.

        Walks the persistent parent chain and, at each hop, checks an ancestor
        agent span; when ``track_siblings`` is on it also checks a *sibling*
        agent span sharing the current parent. The bounded loop guard
        guarantees termination even in the face of a malformed parent cycle.
        """
        cur_sid = self._span_id(span)
        for _ in range(64):
            if cur_sid is None:
                return None
            parent_sid = self._parent_by_span_id.get(cur_sid)
            if parent_sid is None:
                return None
            agent = self._agent_by_span_id.get(parent_sid)
            if agent is not None:
                return agent
            if self._track_siblings:
                sibling_agent = self._agent_by_parent_span_id.get(parent_sid)
                if sibling_agent is not None:
                    return sibling_agent
            cur_sid = parent_sid
        return None


# ---------------------------------------------------------------------------
# Exporter swapping on existing span processors
# ---------------------------------------------------------------------------


def get_processor_exporter(processor: SpanProcessor) -> Optional[SpanExporter]:
    """Read the underlying exporter on a span processor across OTEL SDK versions.

    Mirrors :func:`set_processor_exporter` so the read and write paths use the
    same detection. Today both layouts resolve via the public ``span_exporter``
    attribute (newer ``BatchSpanProcessor`` exposes it as a property that
    delegates to ``self._batch_processor._exporter``), but probing the inner
    slot first is defense-in-depth: if a future OTEL release drops the
    convenience property, the reader still finds the exporter the same way the
    writer would set it.
    """
    inner = getattr(processor, "_batch_processor", None)
    if inner is not None:
        exp = getattr(inner, "_exporter", None)
        if exp is not None:
            return exp
    return getattr(processor, "span_exporter", None)


def set_processor_exporter(processor: SpanProcessor, exporter: SpanExporter) -> None:
    """Set the underlying exporter on a span processor across OTEL SDK versions.

    Works for both :class:`BatchSpanProcessor` and :class:`SimpleSpanProcessor`:

    - Newer ``BatchSpanProcessor`` exposes the exporter as a read-only property
      that delegates to ``self._batch_processor._exporter``; we set the inner
      slot directly.
    - Older ``BatchSpanProcessor`` and ``SimpleSpanProcessor`` keep
      ``span_exporter`` as a plain settable attribute.

    We try the inner attribute first (newer Batch layout), then fall back to
    direct assignment (Simple / older Batch).
    """
    inner = getattr(processor, "_batch_processor", None)
    if inner is not None and hasattr(inner, "_exporter"):
        inner._exporter = exporter  # noqa: SLF001
        return
    # Older OTEL Batch SDK or SimpleSpanProcessor: span_exporter is a plain
    # attribute we can set directly.
    processor.span_exporter = exporter


# ---------------------------------------------------------------------------
# Content-capture opt-out (shared env var across integrations)
# ---------------------------------------------------------------------------

# Opt-out env var for message/tool content capture. When truthy, integrations
# disable their framework's sensitive-data capture so prompts, completions,
# and tool arguments/results are NOT captured into spans.
DISABLE_CONTENT_CAPTURE_ENV = "RHESIS_DISABLE_CONTENT_CAPTURE"

# Truthy string values for opt-in/out env vars.
TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def content_capture_enabled() -> bool:
    """Return whether frameworks should capture message/tool content into spans.

    Defaults to ``True`` because the whole point of the Rhesis integration is
    to ship prompts/completions/tool I/O to the backend so they render in the
    trace UI. Privacy-sensitive deployments can opt out by setting
    ``RHESIS_DISABLE_CONTENT_CAPTURE`` to a truthy value (``1``/``true``/
    ``yes``/``on``).
    """
    raw = os.getenv(DISABLE_CONTENT_CAPTURE_ENV)
    if raw is None:
        return True
    return raw.strip().lower() not in TRUTHY_ENV_VALUES
