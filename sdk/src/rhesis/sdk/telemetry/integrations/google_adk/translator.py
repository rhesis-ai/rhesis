"""Span translator for Google ADK spans.

Google ADK emits OpenTelemetry spans natively, unconditionally, as soon as a
``TracerProvider`` exists. There is nothing to turn on and nothing to
monkey-patch: we let ADK emit its spans and translate them on the way out, using
the same exporter-wrapper architecture as the MAF and Pydantic AI integrations
(see :mod:`rhesis.sdk.telemetry.integrations.agent_framework.translator`).

Three things make ADK harder than those two.

**Two spans per model call.** ADK wraps every model call in ``call_llm`` and then
opens ``generate_content {model}`` inside it. They describe the same call, so
only one may become ``ai.llm.invoke``. We keep ``call_llm`` -- it is the only one
carrying prompt/completion content with default settings, and it has the fuller
token breakdown -- and drop ``generate_content``. Because ``generate_content`` is
the structural *parent* of the ``execute_tool`` spans (ADK opens the tool spans
while the model-call async generator is still suspended inside its span),
dropping it would orphan every tool span, so surviving children are re-pointed at
the nearest ancestor we kept. ``generate_content`` is promoted to
``ai.llm.invoke`` itself when no ``call_llm`` ancestor exists, which covers both
a future ADK that finishes removing ``call_llm`` and ADK's deprecated
``use_generate_content_span`` path.

**Two multi-agent mechanisms, with different span shapes.** ``transfer_to_agent``
surfaces as a tool span whose args name the target, and the target agent's own
``invoke_agent`` span is a *sibling* of the caller's rather than a child -- so the
tool span is the only place that edge is observable, and it becomes the
``ai.agent.handoff`` span directly. ``AgentTool`` instead nests a whole inner
``Runner`` beneath ``execute_tool``, so its edge is synthesized the way the
Pydantic AI integration does it: an ``invoke_agent`` span whose ancestor chain
contains a *different* agent gets an extra ``ai.agent.handoff`` span alongside it.

**The trace root is not identifiable by name.** ADK's root is ``invocation`` under
telemetry schema v1 and ``invoke_workflow {entrypoint}`` under v2, ``run_live``
emits no root span at all, and ``AgentTool``'s inner ``Runner`` emits a second,
*nested* ``invocation`` / ``invoke_workflow``. Turn-root stamping therefore keys
off ``parent is None`` and never off the span name.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable, Mapping, Sequence

from opentelemetry.sdk.trace import Event, ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from opentelemetry.trace import SpanContext, SpanKind, TraceFlags
from opentelemetry.trace.status import Status, StatusCode

from rhesis.sdk.telemetry.integrations.genai import (
    KEEP_PARENT,
    TRUTHY_ENV_VALUES,
    AncestryRegistry,
    TranslatedSpan,
    content_capture_enabled,
    translate_events,
)
from rhesis.sdk.telemetry.integrations.google_adk import mapping
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.context import (
    get_conversation_id,
    is_llm_observation_active,
    set_llm_observation_active,
)
from rhesis.telemetry.schemas import AIOperationType

logger = logging.getLogger(__name__)

# Opt back in to the ADK infrastructure spans we drop by default. Mirrors
# ``RHESIS_MAF_VERBOSE_WORKFLOW_SPANS``: opt-in, default off (note the asymmetry
# with content capture, which is opt-*out*, default on).
VERBOSE_SPANS_ENV = "RHESIS_GOOGLE_ADK_VERBOSE_SPANS"

# Shared id generator for synthesized handoff spans. OTel's TracerProvider does
# not expose its generator, so we use a fresh RandomIdGenerator; collisions with
# real span ids are astronomically unlikely (64-bit random).
_id_generator = RandomIdGenerator()


def verbose_spans_enabled() -> bool:
    """Return whether ADK infrastructure spans should be forwarded."""
    raw = os.getenv(VERBOSE_SPANS_ENV)
    if raw is None:
        return False
    return raw.strip().lower() in TRUTHY_ENV_VALUES


def _is_adk_span(span: ReadableSpan) -> bool:
    scope = getattr(span, "instrumentation_scope", None)
    return mapping.is_adk_scope(getattr(scope, "name", None))


# ---------------------------------------------------------------------------
# Span index: ancestry, drop-and-reparent, and the semconv message stash
# ---------------------------------------------------------------------------


class _ADKSpanIndex(AncestryRegistry):
    """Persistent, process-lifetime index of ADK span structure.

    Everything here is recorded at span *start*, which is the only point where
    the information is guaranteed available: a parent always starts before its
    children, whereas under ``BatchSpanProcessor`` a child *ends* (and exports)
    before its parent, so a batch-local parent walk misses ancestors on long
    runs.

    On top of the inherited parent/agent index it keeps:

    - ``_parent_ctx_by_span_id`` -- the full parent ``SpanContext``, not just the
      id, because re-pointing a child needs a context object to hand to
      :class:`~rhesis.sdk.telemetry.integrations.genai.TranslatedSpan`.
    - ``_name_by_span_id`` -- so the reparent walk can ask "was this ancestor one
      of the spans we drop?" without having the ancestor span in hand.
    - ``_call_llm_ids`` -- lets a ``generate_content`` span decide whether it is
      the duplicate inner model span (drop) or the only one (promote).
    - ``_semconv_by_parent`` -- the standard ``gen_ai.*.messages`` attributes
      salvaged from a dropped ``generate_content`` span, keyed by its parent
      ``call_llm`` span id.

    Sibling tracking stays **off**. ADK's ``AgentTool`` delegation nests properly
    (``invoke_agent`` child -> ... -> ``execute_tool`` -> ``call_llm`` ->
    ``invoke_agent`` parent), and with siblings on a delegated agent span would
    resolve *itself* through its own parent entry and report its own name as the
    calling agent.

    ``invoke_workflow`` is deliberately **not** registered as an agent-name
    prefix. Under schema v2 an ``AgentTool``'s inner root is
    ``invoke_workflow {sub_agent}`` -- the same name as the sub-agent -- so
    registering it would make the delegated agent resolve ``from == to`` and the
    handoff edge would silently vanish.
    """

    def __init__(self, max_entries: int = 8192) -> None:
        super().__init__(
            agent_name_prefix=mapping.INVOKE_AGENT_NAME_PREFIX,
            track_siblings=False,
            max_entries=max_entries,
        )
        self._parent_ctx_by_span_id: dict[int, Any] = {}
        self._name_by_span_id: dict[int, str] = {}
        self._call_llm_ids: dict[int, bool] = {}
        self._semconv_by_parent: dict[int, dict[str, Any]] = {}

    def _bounded_set(self, store: dict, key: Any, value: Any) -> None:
        if len(store) >= self._max_entries:
            try:
                store.pop(next(iter(store)), None)
            except StopIteration:  # pragma: no cover - racy but harmless
                pass
        store[key] = value

    def record(self, span: Any) -> None:
        """Index a span's structure. Safe for ``on_start``; never raises."""
        super().record(span)
        try:
            span_id = self._span_id(span)
            if span_id is None:
                return
            name = getattr(span, "name", "") or ""
            self._bounded_set(self._name_by_span_id, span_id, name)
            self._bounded_set(self._parent_ctx_by_span_id, span_id, getattr(span, "parent", None))
            if mapping.is_call_llm_span(name):
                self._bounded_set(self._call_llm_ids, span_id, True)
        except Exception:  # noqa: BLE001 - recording must never break tracing
            logger.debug("Failed to record ADK span structure", exc_info=True)

    def name_of(self, span_id: int | None) -> str | None:
        """Return the recorded original span name for ``span_id``."""
        if span_id is None:
            return None
        return self._name_by_span_id.get(span_id)

    def knows(self, span_id: int | None) -> bool:
        """Return True if ``span_id`` belongs to an ADK span we indexed."""
        return span_id is not None and span_id in self._name_by_span_id

    def has_call_llm_ancestor(self, span_id: int | None) -> bool:
        """Return True if any ancestor of ``span_id`` is a ``call_llm`` span."""
        cur_sid = span_id
        for _ in range(64):
            if cur_sid is None:
                return False
            parent_sid = self._parent_by_span_id.get(cur_sid)
            if parent_sid is None:
                return False
            if parent_sid in self._call_llm_ids:
                return True
            cur_sid = parent_sid
        return False

    def is_adk_root(self, span: Any) -> bool:
        """Return True for the outermost ADK span of its trace.

        True both for a real trace root and for an ADK run nested directly inside
        a non-ADK span (a Rhesis ``@endpoint`` / ``@observe`` span). That is the
        span where the per-trace conversation entry must be released -- but *not*
        the nested ``invocation`` / ``invoke_workflow`` that ``AgentTool``'s inner
        ``Runner`` emits, whose parent is itself an ADK span and which ends
        before the real root.
        """
        parent_sid = getattr(getattr(span, "parent", None), "span_id", None)
        if parent_sid is None:
            return True
        return not self.knows(parent_sid)

    def resolve_parent(self, span: Any, is_dropped: Callable[[str, int], bool]) -> Any:
        """Return the parent context to use once dropped ancestors are skipped.

        Walks up while each ancestor is a span the exporter is dropping, so a
        chain of drops (``handle_context_caching`` inside ``generate_content``,
        say) collapses in one pass. Returns :data:`KEEP_PARENT` when the
        immediate parent survives, so the caller does no work in the common case.
        """
        try:
            parent_ctx = getattr(span, "parent", None)
            parent_sid = getattr(parent_ctx, "span_id", None)
            if parent_sid is None:
                return KEEP_PARENT
            changed = False
            for _ in range(64):
                name = self._name_by_span_id.get(parent_sid)
                if name is None or not is_dropped(name, parent_sid):
                    return parent_ctx if changed else KEEP_PARENT
                parent_ctx = self._parent_ctx_by_span_id.get(parent_sid)
                parent_sid = getattr(parent_ctx, "span_id", None)
                changed = True
                if parent_sid is None:
                    return parent_ctx
            return parent_ctx
        except Exception:  # noqa: BLE001 - must never break tracing
            logger.debug("Failed to resolve ADK parent context", exc_info=True)
            return KEEP_PARENT

    def stash_semconv_messages(self, span: ReadableSpan) -> None:
        """Salvage a dropped model span's standard GenAI message attributes.

        ADK puts ``gen_ai.input.messages`` / ``.output.messages`` /
        ``.system_instructions`` on ``generate_content``, which we drop -- but
        only when the app has opted into the experimental GenAI semconv, in
        which case they are better than parsing the raw blobs. The child always
        ends before its ``call_llm`` parent, which itself ends before it is
        exported, so stashing here is always visible by the time the parent is
        translated.
        """
        try:
            attrs = span.attributes or {}
            if not mapping.has_semconv_messages(attrs):
                return
            parent_sid = getattr(getattr(span, "parent", None), "span_id", None)
            if parent_sid is None:
                return
            self._bounded_set(
                self._semconv_by_parent, parent_sid, mapping.semconv_message_carrier(attrs)
            )
        except Exception:  # noqa: BLE001 - must never break tracing
            logger.debug("Failed to stash ADK semconv messages", exc_info=True)

    def take_semconv_messages(self, span: Any) -> dict[str, Any] | None:
        """Pop the messages stashed by this span's dropped model child."""
        span_id = self._span_id(span)
        if span_id is None:
            return None
        return self._semconv_by_parent.pop(span_id, None)


# Shared singleton: the dedup processor populates it at span start/end, the
# translating exporter reads it at export time. Both live in this module, so a
# module-level instance is the simplest correct wiring.
_span_index = _ADKSpanIndex()


# ---------------------------------------------------------------------------
# Per-trace conversation content
# ---------------------------------------------------------------------------


class _ConversationContentRegistry:
    """Process-lifetime store of per-trace conversation input/output text.

    ADK's trace root carries almost nothing: the v1 ``invocation`` span has *zero*
    attributes, and the v2 ``invoke_workflow`` span has only the workflow name and
    session id. The user's query and the final answer live on the nested
    ``call_llm`` spans. To let a plain ``auto_instrument("google_adk")`` run show
    up in the Conversation tab, we record them here at span end, keyed by trace
    id, and stamp them onto the root when it is exported.

    Unlike the MAF registry this does **not** use first-recorded-wins. ADK's
    ``AgentTool`` runs a sub-agent inside the caller's model call, so the
    sub-agent's ``call_llm`` span *ends first* and first-wins would capture the
    sub-agent's internal prompt as the conversation input. We compare span
    timestamps instead: the input comes from the earliest-**started** model span
    and the output from the latest-**ended** one. That is right for ``AgentTool``,
    for ``transfer_to_agent`` (where the target agent answers last), and for the
    plain single-agent case.

    The ADK session id is picked by the same earliest-started rule, because
    ``AgentTool``'s inner ``Runner`` creates its own ephemeral session with a
    *different* id inside the same trace.

    A Rhesis conversation id (set by the app via
    ``rhesis.telemetry.context.set_conversation_id``) is recorded at span start
    while that contextvar is still live, and takes precedence over the ADK
    session id. All stores are bounded and strings are truncated to
    :data:`~rhesis.telemetry.constants.ConversationContext.MAX_IO_LENGTH` at
    record time.
    """

    def __init__(self, max_entries: int = 4096) -> None:
        self._input_by_trace: dict[int, tuple[int, str]] = {}
        self._output_by_trace: dict[int, tuple[int, str]] = {}
        self._adk_session_by_trace: dict[int, tuple[int, str]] = {}
        self._rhesis_conversation_by_trace: dict[int, str] = {}
        self._max_entries = max_entries
        self._lock = threading.Lock()

    def _evict_if_needed(self, store: dict) -> None:
        if len(store) < self._max_entries:
            return
        try:
            store.pop(next(iter(store)), None)
        except StopIteration:  # pragma: no cover - racy but harmless
            pass

    def _record_earliest(
        self, store: dict[int, tuple[int, str]], trace_id: int, order: int, value: str
    ) -> None:
        existing = store.get(trace_id)
        if existing is None:
            self._evict_if_needed(store)
        elif existing[0] <= order:
            return
        store[trace_id] = (order, value)

    def _record_latest(
        self, store: dict[int, tuple[int, str]], trace_id: int, order: int, value: str
    ) -> None:
        existing = store.get(trace_id)
        if existing is None:
            self._evict_if_needed(store)
        elif existing[0] > order:
            return
        store[trace_id] = (order, value)

    def record_model_span(
        self,
        trace_id: int | None,
        *,
        start_time: int | None,
        end_time: int | None,
        input_text: str | None = None,
        output_text: str | None = None,
        adk_session_id: str | None = None,
    ) -> None:
        """Record one model span's contribution to its trace. Never raises."""
        if trace_id is None:
            return
        max_len = ConversationContext.MAX_IO_LENGTH
        start = start_time if start_time is not None else 0
        end = end_time if end_time is not None else 0
        try:
            with self._lock:
                if input_text:
                    self._record_earliest(
                        self._input_by_trace, trace_id, start, input_text[:max_len]
                    )
                if output_text:
                    self._record_latest(self._output_by_trace, trace_id, end, output_text[:max_len])
                if adk_session_id:
                    self._record_earliest(
                        self._adk_session_by_trace, trace_id, start, adk_session_id
                    )
        except Exception:  # noqa: BLE001 - recording must never break tracing
            logger.debug("Failed to record ADK conversation content", exc_info=True)

    def record_rhesis_conversation_id(
        self, trace_id: int | None, conversation_id: str | None
    ) -> None:
        """Record the app-supplied Rhesis conversation id. Never raises."""
        if trace_id is None or not conversation_id:
            return
        try:
            with self._lock:
                if trace_id not in self._rhesis_conversation_by_trace:
                    self._evict_if_needed(self._rhesis_conversation_by_trace)
                    self._rhesis_conversation_by_trace[trace_id] = conversation_id
        except Exception:  # noqa: BLE001 - recording must never break tracing
            logger.debug("Failed to record ADK conversation id", exc_info=True)

    def consume(self, trace_id: int | None) -> tuple[str | None, str | None, str | None]:
        """Pop and return ``(conversation_id, input, output)`` for ``trace_id``.

        Called exactly once per trace, when its root span is exported, so entries
        do not linger for the process lifetime even when the run was nested under
        a Rhesis ``@endpoint`` span and nothing gets stamped.
        """
        if trace_id is None:
            return None, None, None
        with self._lock:
            rhesis_id = self._rhesis_conversation_by_trace.pop(trace_id, None)
            adk_session = self._adk_session_by_trace.pop(trace_id, None)
            conv_input = self._input_by_trace.pop(trace_id, None)
            conv_output = self._output_by_trace.pop(trace_id, None)
        conversation_id = rhesis_id or (adk_session[1] if adk_session else None)
        return (
            conversation_id,
            conv_input[1] if conv_input else None,
            conv_output[1] if conv_output else None,
        )


_conversation_content = _ConversationContentRegistry()


def conversation_root_attributes(span: ReadableSpan) -> dict[str, Any] | None:
    """Build Rhesis conversation attributes for an ADK trace-root span.

    Always consumes the per-trace entry so it does not linger when the ADK run is
    nested under a Rhesis ``@endpoint`` / ``@observe`` parent (the long-running
    service path). Stamping is limited to trace roots (``parent is None``):
    inside an enclosing Rhesis span, that span owns turn-root semantics and the
    ADK root must not claim them again.

    Deliberately keyed on "is the trace root" rather than on the span name. ADK's
    root is ``invocation`` under schema v1 and ``invoke_workflow {entrypoint}``
    under v2, ``run_live`` emits no root span so ``invoke_agent`` is the top, and
    ``AgentTool`` emits a second *nested* ``invocation`` that must never be
    treated as a turn root.

    A conversation id promotes the span to a multi-turn turn root; input/output
    alone still get stamped so a one-shot run shows its conversation content.
    """
    if not _span_index.is_adk_root(span):
        return None

    ctx = getattr(span, "context", None)
    trace_id = getattr(ctx, "trace_id", None)
    conversation_id, conv_input, conv_output = _conversation_content.consume(trace_id)

    # Released above but not stamped: an enclosing Rhesis span owns turn-root
    # semantics for this trace.
    if getattr(span, "parent", None) is not None:
        return None

    attrs: dict[str, Any] = {}
    if conversation_id:
        attrs[ConversationContext.SpanAttributes.IS_TURN_ROOT] = True
        attrs[ConversationContext.SpanAttributes.CONVERSATION_ID] = conversation_id
    if conv_input:
        attrs[ConversationContext.SpanAttributes.CONVERSATION_INPUT] = conv_input
    if conv_output:
        attrs[ConversationContext.SpanAttributes.CONVERSATION_OUTPUT] = conv_output
    return attrs or None


# ---------------------------------------------------------------------------
# Span translation
# ---------------------------------------------------------------------------


def translate_span(
    span: ReadableSpan,
    extra_attributes: Mapping[str, Any] | None = None,
    *,
    new_parent: Any = KEEP_PARENT,
    semconv_messages: Mapping[str, Any] | None = None,
    capture_content: bool | None = None,
    name_override: str | None = None,
) -> TranslatedSpan:
    """Build the translated wrapper for a single ADK span.

    Pure function so it is trivially testable without an exporter.

    Model-call spans get ``ai.prompt`` / ``ai.completion`` events and tool spans
    get ``ai.tool.input`` / ``ai.tool.output`` events, both extracted from ADK's
    own JSON blob attributes (or from the standard GenAI message attributes when
    the app opted into the experimental semconv).
    """
    raw_attrs = span.attributes or {}
    new_name = name_override or mapping.translate_span_name(span.name, raw_attrs)
    new_attrs = mapping.translate_attributes(raw_attrs)
    # When we land in the ``function.google_adk.*`` fallback (because ADK added a
    # span we do not map), keep the original name as an attribute so the trace
    # stays debuggable downstream.
    if new_name.startswith("function.google_adk.") and span.name and span.name != new_name:
        new_attrs.setdefault(mapping.ORIGINAL_SPAN_NAME, span.name)
    if extra_attributes:
        new_attrs.update(extra_attributes)

    new_events = list(translate_events(span.events or (), raw_attrs))
    if capture_content is None:
        capture_content = content_capture_enabled()
    if capture_content:
        synthesized = mapping.synthesize_llm_content_events(
            raw_attrs, semconv_messages=semconv_messages
        )
        synthesized += mapping.synthesize_tool_io_events(raw_attrs)
        for synth_name, synth_attrs in synthesized:
            new_events.append(Event(name=synth_name, attributes=synth_attrs))

    return TranslatedSpan(span, new_name, new_attrs, new_events, new_parent)


def translate_handoff_span(
    span: ReadableSpan,
    *,
    from_agent: str | None,
    to_agent: str,
    new_parent: Any = KEEP_PARENT,
) -> TranslatedSpan:
    """Translate an ``execute_tool transfer_to_agent`` span into a handoff span.

    ``transfer_to_agent`` is ADK's ``sub_agents`` delegation primitive rather than
    a domain tool, and the target agent's ``invoke_agent`` span is emitted as a
    *sibling* of the caller's -- so this span is the only place the edge exists.
    Translating it in place (rather than synthesizing a second span next to it)
    keeps the trace honest: there is exactly one row, and it is the handoff.
    """
    raw_attrs = span.attributes or {}
    new_attrs = mapping.translate_handoff_attributes(
        raw_attrs, from_agent=from_agent, to_agent=to_agent
    )
    new_events = list(translate_events(span.events or (), raw_attrs))
    return TranslatedSpan(
        span,
        AIOperationType.AGENT_HANDOFF.value,
        new_attrs,
        new_events,
        new_parent,
    )


def synthesize_handoff_span(
    agent_span: ReadableSpan,
    from_agent: str,
    to_agent: str,
    *,
    parent: Any = KEEP_PARENT,
) -> ReadableSpan | None:
    """Build an ``ai.agent.handoff`` span for an ``AgentTool`` delegation.

    Called when an ``invoke_agent`` span turns out to have been invoked from
    inside another agent's tool call (its ancestor chain contains a different
    agent). The synthesized span gets a brand-new ``span_id``, shares the agent
    span's ``trace_id``, is parented alongside the delegated run, and is
    zero-duration at the agent span's start time -- the moment the handoff
    happened.

    Returns ``None`` when the agent span lacks a usable span context.
    """
    ctx = getattr(agent_span, "context", None)
    trace_id = getattr(ctx, "trace_id", None)
    if trace_id is None:
        return None

    trace_flags = getattr(ctx, "trace_flags", None) or TraceFlags(TraceFlags.SAMPLED)
    start_time = getattr(agent_span, "start_time", None)
    resolved_parent = getattr(agent_span, "parent", None) if parent is KEEP_PARENT else parent

    new_ctx = SpanContext(
        trace_id=trace_id,
        span_id=_id_generator.generate_span_id(),
        is_remote=False,
        trace_flags=trace_flags,
    )
    return ReadableSpan(
        name=AIOperationType.AGENT_HANDOFF.value,
        context=new_ctx,
        parent=resolved_parent,
        resource=getattr(agent_span, "resource", None),
        attributes={
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_AGENT_HANDOFF,
            AIAttributes.AGENT_HANDOFF_FROM: from_agent,
            AIAttributes.AGENT_HANDOFF_TO: to_agent,
        },
        events=(),
        kind=SpanKind.INTERNAL,
        instrumentation_scope=getattr(agent_span, "instrumentation_scope", None),
        status=Status(StatusCode.OK),
        start_time=start_time,
        end_time=start_time,
    )


def _safe_fallback_span(span: ReadableSpan) -> ReadableSpan:
    """Build the safest possible wrapper when :func:`translate_span` raises.

    Raw ADK span names (``"invoke_agent root_agent"``, ``"call_llm"``, ...) all
    fail the backend's :func:`~rhesis.telemetry.attributes.validate_span_name`
    check, so forwarding the original span on a translation error means a silent
    HTTP 422 drop. Funnel it into ``function.google_adk.*`` instead, keeping the
    original name as an attribute.
    """
    original_name = getattr(span, "name", None) or ""
    fallback_name = mapping.fallback_function_adk_name(original_name)
    raw_attrs = dict(span.attributes or {})
    if original_name and original_name != fallback_name:
        raw_attrs.setdefault(mapping.ORIGINAL_SPAN_NAME, original_name)
    try:
        return TranslatedSpan(span, fallback_name, raw_attrs, tuple(span.events or ()))
    except Exception:  # noqa: BLE001 - the wrapper itself must never raise
        logger.debug("Failed to build fallback TranslatedSpan; forwarding original", exc_info=True)
        return span


def _build_batch_lookups(
    spans: Sequence[ReadableSpan],
) -> tuple[dict[int, str], dict[int, ReadableSpan]]:
    """Index ADK spans in the batch by ``span_id`` for parent walks.

    Batch-local fallback for when the persistent index has no entry (e.g. the
    integration was enabled with a processor that never saw ``on_start``).
    """
    agent_by_span_id: dict[int, str] = {}
    span_by_id: dict[int, ReadableSpan] = {}
    for span in spans:
        if not _is_adk_span(span):
            continue
        ctx = getattr(span, "context", None)
        sid = getattr(ctx, "span_id", None)
        if sid is None:
            continue
        span_by_id[sid] = span
        attrs = span.attributes or {}
        if mapping.is_agent_span(attrs, span.name):
            name = mapping.agent_name(attrs, span.name)
            if name:
                agent_by_span_id[sid] = name
    return agent_by_span_id, span_by_id


def _find_ancestor_agent_in_batch(
    span: ReadableSpan,
    agent_by_span_id: dict[int, str],
    span_by_id: dict[int, ReadableSpan],
) -> str | None:
    """Walk the OTel parent chain within the batch to find the calling agent."""
    cur: ReadableSpan | None = span
    for _ in range(32):
        if cur is None:
            return None
        parent_sid = getattr(getattr(cur, "parent", None), "span_id", None)
        if parent_sid is None:
            return None
        if parent_sid in agent_by_span_id:
            return agent_by_span_id[parent_sid]
        cur = span_by_id.get(parent_sid)
    return None


class GoogleADKTranslatingExporter(SpanExporter):
    """Wrap any ``SpanExporter`` and rewrite Google ADK spans on their way out.

    Non-ADK spans (LangChain, MAF, ``@observe``, ``@endpoint``, manual spans, ...)
    pass through untouched. Only spans whose instrumentation scope is exactly
    ``gcp.vertex.agent`` are translated.

    Never raises: a span whose translation fails is forwarded under a
    validator-safe ``function.google_adk.*`` name instead of being dropped or
    rejected.
    """

    def __init__(self, wrapped: SpanExporter, *, verbose_spans: bool | None = None) -> None:
        self._wrapped = wrapped
        self._verbose_spans = verbose_spans_enabled() if verbose_spans is None else verbose_spans

    @property
    def wrapped(self) -> SpanExporter:
        """The underlying exporter (e.g. ``RhesisOTLPExporter``)."""
        return self._wrapped

    @property
    def verbose_spans(self) -> bool:
        """Whether ADK infrastructure spans are forwarded rather than dropped."""
        return self._verbose_spans

    def _is_dropped(self, original_name: str, span_id: int) -> bool:
        """Whether the exporter drops the span with this name and id.

        Also used as the predicate for the reparent walk, so a child of a dropped
        span inherits the nearest ancestor we actually keep.
        """
        if self._verbose_spans:
            return False
        if mapping.is_low_value_span(original_name):
            return True
        if mapping.is_model_span(original_name):
            # Only the *duplicate* inner model span is dropped. Without a
            # ``call_llm`` ancestor this span is the only record of the model
            # call, so it is kept and promoted to ``ai.llm.invoke`` instead.
            return _span_index.has_call_llm_ancestor(span_id)
        return False

    def _infra_name_override(self, original_name: str, span_id: int | None) -> str | None:
        """Force a ``function.google_adk.*`` name for a span only verbose mode kept.

        Reached only with ``RHESIS_GOOGLE_ADK_VERBOSE_SPANS`` set, where
        :meth:`_is_dropped` returns ``False`` for everything. Without this, the
        duplicate ``generate_content`` span would translate to a second
        ``ai.llm.invoke`` for one model call and ``execute_tool (merged)`` would
        look like a real tool call.
        """
        if not self._verbose_spans:
            return None
        if mapping.is_low_value_span(original_name) or (
            mapping.is_model_span(original_name) and _span_index.has_call_llm_ancestor(span_id)
        ):
            return mapping.infra_span_name(original_name)
        return None

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        agent_by_span_id, span_by_id = _build_batch_lookups(spans)
        capture_content = content_capture_enabled()

        translated: list[ReadableSpan] = []
        for span in spans:
            if not _is_adk_span(span):
                translated.append(span)
                continue
            try:
                forwarded = self._translate_adk_span(
                    span,
                    agent_by_span_id=agent_by_span_id,
                    span_by_id=span_by_id,
                    capture_content=capture_content,
                )
                translated.extend(forwarded)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to translate Google ADK span %r; falling back to "
                    "function.google_adk.* name so the backend still accepts it",
                    getattr(span, "name", "?"),
                    exc_info=True,
                )
                translated.append(_safe_fallback_span(span))
        return self._wrapped.export(translated)

    def _translate_adk_span(
        self,
        span: ReadableSpan,
        *,
        agent_by_span_id: dict[int, str],
        span_by_id: dict[int, ReadableSpan],
        capture_content: bool,
    ) -> list[ReadableSpan]:
        """Translate one ADK span into zero, one, or two spans to forward."""
        original_name = span.name or ""
        span_id = getattr(getattr(span, "context", None), "span_id", None)
        raw_attrs = span.attributes or {}

        if span_id is not None and self._is_dropped(original_name, span_id):
            return []

        new_parent = _span_index.resolve_parent(span, self._is_dropped)

        # A dropped ``generate_content`` child may have salvaged the standard
        # GenAI message attributes for this ``call_llm`` span.
        semconv_messages = (
            _span_index.take_semconv_messages(span)
            if mapping.is_call_llm_span(original_name)
            else None
        )

        if mapping.is_transfer_tool_span(raw_attrs):
            to_agent = mapping.transfer_target(raw_attrs)
            if to_agent:
                from_agent = _span_index.find_ancestor_agent(span) or _find_ancestor_agent_in_batch(
                    span, agent_by_span_id, span_by_id
                )
                return [
                    translate_handoff_span(
                        span,
                        from_agent=from_agent,
                        to_agent=to_agent,
                        new_parent=new_parent,
                    )
                ]
            # Content capture is off, so the target is unknowable and a handoff
            # with no destination draws no edge. Keep it as a plain tool span.

        forwarded: list[ReadableSpan] = [
            translate_span(
                span,
                conversation_root_attributes(span),
                new_parent=new_parent,
                semconv_messages=semconv_messages,
                capture_content=capture_content,
                name_override=self._infra_name_override(original_name, span_id),
            )
        ]

        # ``AgentTool`` delegation: a nested agent run whose ancestor chain holds
        # a different agent. ``transfer_to_agent`` never reaches here, because the
        # target's ``invoke_agent`` span is a *sibling* of the caller's, so the
        # ancestor walk finds no agent -- which is exactly what stops the two
        # mechanisms from double-counting the same edge.
        if mapping.is_agent_span(raw_attrs, original_name):
            to_agent = mapping.agent_name(raw_attrs, original_name)
            if to_agent:
                from_agent = _span_index.find_ancestor_agent(span) or _find_ancestor_agent_in_batch(
                    span, agent_by_span_id, span_by_id
                )
                if from_agent and from_agent != to_agent:
                    handoff = synthesize_handoff_span(span, from_agent, to_agent, parent=new_parent)
                    if handoff is not None:
                        forwarded.append(handoff)

        return forwarded

    def shutdown(self) -> None:
        try:
            self._wrapped.shutdown()
        except Exception:  # noqa: BLE001
            logger.debug("Wrapped exporter shutdown failed", exc_info=True)

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        try:
            return bool(self._wrapped.force_flush(timeout_millis))
        except Exception:  # noqa: BLE001
            logger.debug("Wrapped exporter force_flush failed", exc_info=True)
            return False


class GoogleADKLLMDedupSpanProcessor(SpanProcessor):
    """Span processor for ADK span indexing, conversation capture, and LLM dedup.

    Three responsibilities, all needing span *start* / *end* hooks that the
    exporter wrapper does not get:

    1. Records every ADK span's structure into the module-level
       :class:`_ADKSpanIndex`, so the exporter can resolve handoff ``from``
       agents and re-point children of dropped spans across export batches.
    2. Captures the per-trace conversation input/output and session id from
       ``call_llm`` spans at ``on_end``, and the app's Rhesis conversation id at
       ``on_start`` while that contextvar is still live.
    3. Toggles :func:`~rhesis.telemetry.context.is_llm_observation_active` for the
       duration of ADK model spans, so a flag-checking auto-instrumentation
       running in the same process (e.g. the LangChain callback handler) does not
       emit a second ``ai.llm.invoke`` for the same call.

    At ``on_start`` ADK has not yet assigned any attributes -- ``trace_call_llm``
    runs much later -- so model spans are detected from their *name* and the
    previous flag value is stashed keyed by span id. Sidecar attributes on the
    span object are not an option: ``on_start`` receives a writable ``_Span``
    while ``on_end`` receives a different ``ReadableSpan`` snapshot built from it.

    :meth:`activate` / :meth:`deactivate` let the integration's ``disable()``
    neutralize the processor without removing it from the ``TracerProvider``
    (OTEL exposes no removal API).
    """

    def __init__(self) -> None:
        self._active = False
        self._prev_flags: dict[int, bool] = {}
        self._PREV_FLAGS_MAX = 4096

    def activate(self) -> None:
        """Mark the processor active so ``on_start``/``on_end`` do their work."""
        self._active = True

    def deactivate(self) -> None:
        """Mark the processor inactive; subsequent hooks are no-ops."""
        self._active = False
        self._prev_flags.clear()

    @staticmethod
    def _span_id(span) -> int | None:
        ctx = getattr(span, "context", None)
        if ctx is None:
            try:
                ctx = span.get_span_context()  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                return None
        return getattr(ctx, "span_id", None)

    @staticmethod
    def _trace_id(span) -> int | None:
        return getattr(getattr(span, "context", None), "trace_id", None)

    def _store_prev_flag(self, span, prev: bool) -> None:
        span_id = self._span_id(span)
        if span_id is None:
            return
        if len(self._prev_flags) >= self._PREV_FLAGS_MAX:
            try:
                self._prev_flags.pop(next(iter(self._prev_flags)), None)
            except StopIteration:  # pragma: no cover - racy but harmless
                pass
        self._prev_flags[span_id] = prev

    def on_start(self, span, parent_context=None) -> None:  # noqa: D401
        if not self._active:
            return
        try:
            scope = getattr(span, "instrumentation_scope", None)
            if not mapping.is_adk_scope(getattr(scope, "name", None)):
                return
            # Index every ADK span, not just model/agent ones, so the full parent
            # chain is known before any of them export.
            _span_index.record(span)

            # Read the app's conversation id here: by ``on_end`` the caller's
            # contextvar may already have been restored.
            _conversation_content.record_rhesis_conversation_id(
                self._trace_id(span), get_conversation_id()
            )

            span_name = getattr(span, "name", "") or ""
            if not (mapping.is_call_llm_span(span_name) or mapping.is_model_span(span_name)):
                return
            prev = is_llm_observation_active()
            self._store_prev_flag(span, prev)
            if not prev:
                set_llm_observation_active(True)
        except Exception:  # noqa: BLE001 - on_start must never raise
            logger.debug("GoogleADKLLMDedupSpanProcessor.on_start failed", exc_info=True)

    def on_end(self, span: ReadableSpan) -> None:
        if not self._active:
            return
        try:
            if not _is_adk_span(span):
                return
            self._capture_conversation(span)

            # Restore based on what on_start actually recorded rather than
            # re-deriving "is this a model span": if the name shape ever changed,
            # an attribute- or name-gated restore could return early and leave the
            # flag stuck True for the rest of the context. ``_prev_flags`` holds
            # entries only for spans whose start hook toggled it, so membership is
            # the exact restore condition.
            span_id = self._span_id(span)
            if span_id is None or span_id not in self._prev_flags:
                return
            if not bool(self._prev_flags.pop(span_id, False)):
                set_llm_observation_active(False)
        except Exception:  # noqa: BLE001 - on_end must never raise
            logger.debug("GoogleADKLLMDedupSpanProcessor.on_end failed", exc_info=True)

    def _capture_conversation(self, span: ReadableSpan) -> None:
        """Feed a finished model span into the per-trace conversation registry."""
        original_name = span.name or ""
        is_model = mapping.is_model_span(original_name)
        if is_model:
            # The inner model span is usually dropped, so salvage the standard
            # GenAI message attributes for its surviving ``call_llm`` parent.
            _span_index.stash_semconv_messages(span)
        if not (mapping.is_call_llm_span(original_name) or is_model):
            return
        if not content_capture_enabled():
            return
        attrs = span.attributes or {}
        _conversation_content.record_model_span(
            self._trace_id(span),
            start_time=getattr(span, "start_time", None),
            end_time=getattr(span, "end_time", None),
            input_text=mapping.extract_conversation_input(attrs),
            output_text=mapping.extract_conversation_output(attrs),
            adk_session_id=mapping.session_id(attrs),
        )

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True
