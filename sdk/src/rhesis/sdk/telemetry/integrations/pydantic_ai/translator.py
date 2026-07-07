"""Span translator for Pydantic AI spans.

Pydantic AI's built-in instrumentation emits spans natively in the
OpenTelemetry GenAI semantic-convention shape. The Rhesis backend expects
spans in the ``ai.*`` / ``function.*`` schema. Rather than monkey-patching
``Agent.run`` (the previous approach), we let Pydantic AI emit its spans
normally and translate them on their way out.

Architecture: the translator is implemented as a span-exporter wrapper (the
same pattern as the MAF integration, see
:mod:`rhesis.sdk.telemetry.integrations.agent_framework.translator`). We take
the existing exporter that's already attached to the shared
:class:`opentelemetry.sdk.trace.TracerProvider` and wrap it with
:class:`PydanticAITranslatingExporter`. Each batch of spans flows through the
wrapper exactly once: Pydantic AI spans are rewritten, every other span passes
through untouched.

Agent-to-agent delegation ("handoffs"): Pydantic AI has no first-class handoff
primitive — multi-agent delegation is one agent calling another inside a tool.
The trace already nests correctly (child ``invoke_agent`` under the parent's
``execute_tool``), so in addition to translating those spans we *synthesize* an
``ai.agent.handoff`` span whenever an agent run turns out to have been invoked
from inside another agent's tool call. That gives the Rhesis Graph View the
``ai.agent.handoff.from`` / ``.to`` edge it needs to connect the two agents,
mirroring what the MAF integration does for ``HandoffBuilder`` workflows.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from opentelemetry.sdk.trace import Event, ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from opentelemetry.trace import SpanContext, SpanKind, TraceFlags
from opentelemetry.trace.status import Status, StatusCode

from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.sdk.telemetry.context import (
    is_llm_observation_active,
    set_llm_observation_active,
)
from rhesis.sdk.telemetry.integrations.genai import TranslatedSpan, translate_events
from rhesis.sdk.telemetry.integrations.pydantic_ai import mapping

logger = logging.getLogger(__name__)

# Shared id generator for synthesized handoff spans. OTel's TracerProvider
# doesn't expose its generator, so we use a fresh RandomIdGenerator; collisions
# with real span ids are astronomically unlikely (64-bit random).
_id_generator = RandomIdGenerator()

# Pydantic AI names agent-run spans ``invoke_agent <agent_name>`` from the
# start (before attributes are assigned), which is what lets the ancestry
# registry index agents at ``on_start`` time.
_INVOKE_AGENT_NAME_PREFIX = "invoke_agent "


def _is_pydantic_ai_span(span: ReadableSpan) -> bool:
    scope = getattr(span, "instrumentation_scope", None)
    scope_name = getattr(scope, "name", None)
    return mapping.is_pydantic_ai_scope(scope_name)


def translate_span(
    span: ReadableSpan,
    extra_attributes: dict[str, Any] | None = None,
) -> TranslatedSpan:
    """Build the translated wrapper for a single Pydantic AI span.

    Pure function so it's trivially testable without an exporter.

    Chat spans get synthetic ``ai.prompt`` / ``ai.completion`` events from the
    shared GenAI message-attribute helpers; tool spans get ``ai.tool.input`` /
    ``ai.tool.output`` events; agent-run spans get a prompt/completion pair
    from ``pydantic_ai.all_messages`` / ``final_result``.
    """
    raw_attrs = span.attributes or {}
    new_name = mapping.translate_span_name(span.name, raw_attrs)
    new_attrs = mapping.translate_attributes(raw_attrs)
    # When we land in the ``function.pydantic_ai.*`` fallback (because Pydantic
    # AI added a new operation we don't map), preserve the original name as an
    # attribute so the trace remains debuggable downstream.
    if new_name.startswith("function.pydantic_ai.") and span.name and span.name != new_name:
        new_attrs.setdefault("gen_ai.original_span_name", span.name)
    if extra_attributes:
        new_attrs.update(extra_attributes)

    new_events = list(translate_events(span.events or (), raw_attrs))
    for synth_name, synth_attrs in mapping.synthesize_agent_events(raw_attrs):
        new_events.append(Event(name=synth_name, attributes=synth_attrs))

    return TranslatedSpan(span, new_name, new_attrs, new_events)


def synthesize_handoff_span(
    agent_span: ReadableSpan,
    from_agent: str,
    to_agent: str,
) -> ReadableSpan | None:
    """Build an ``ai.agent.handoff`` span for a delegated agent run.

    Called when an ``invoke_agent`` span turns out to have been invoked from
    inside another agent's tool call (its ancestor chain contains a different
    agent). The synthesized span:

    - gets a brand-new ``span_id`` (so it does not collide with real spans),
    - shares the agent span's ``trace_id`` and is parented to the agent span's
      parent (the delegating agent's ``execute_tool`` span), making it a
      sibling of the delegated run in the trace tree,
    - is zero-duration at the agent span's start time (the moment the handoff
      happened),
    - carries ``ai.operation.type = agent.handoff`` plus
      ``ai.agent.handoff.from`` / ``ai.agent.handoff.to``.

    Returns ``None`` when the agent span lacks a usable span context.
    """
    ctx = getattr(agent_span, "context", None)
    trace_id = getattr(ctx, "trace_id", None)
    if trace_id is None:
        return None

    trace_flags = getattr(ctx, "trace_flags", None) or TraceFlags(TraceFlags.SAMPLED)
    start_time = getattr(agent_span, "start_time", None)

    new_ctx = SpanContext(
        trace_id=trace_id,
        span_id=_id_generator.generate_span_id(),
        is_remote=False,
        trace_flags=trace_flags,
    )
    return ReadableSpan(
        name="ai.agent.handoff",
        context=new_ctx,
        parent=getattr(agent_span, "parent", None),
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

    The raw Pydantic AI span name (e.g. ``"chat gpt-4o"``) fails the Rhesis
    backend's :func:`~rhesis.sdk.telemetry.attributes.validate_span_name`
    regex, so simply forwarding the original span on a translation error
    causes silent HTTP 422 drops. Funnel the span into
    ``function.pydantic_ai.*`` instead so the backend accepts it. The original
    name is stashed as ``gen_ai.original_span_name`` for downstream debugging.
    """
    original_name = getattr(span, "name", None) or ""
    fallback_name = mapping.fallback_function_pydantic_ai_name(original_name)
    raw_attrs = dict(span.attributes or {})
    if original_name and original_name != fallback_name:
        raw_attrs.setdefault("gen_ai.original_span_name", original_name)
    raw_events = tuple(span.events or ())
    try:
        return TranslatedSpan(span, fallback_name, raw_attrs, raw_events)
    except Exception:  # noqa: BLE001 - the wrapper itself must never raise
        logger.debug(
            "Failed to build fallback TranslatedSpan; forwarding original",
            exc_info=True,
        )
        return span


class _AncestryRegistry:
    """Persistent (process-lifetime) span ancestry index for handoff edges.

    A batch-local parent walk fails when a delegated ``invoke_agent`` span and
    its enclosing spans are exported in different batches. That is the common
    case under ``BatchSpanProcessor``: a child span ends (and is enqueued)
    *before* its parent, so on long runs the delegating agent's spans land in
    a later batch than the child run that needs them.

    This registry sidesteps batching entirely by recording ancestry at span
    *start* time (a parent always starts before its children, and Pydantic AI
    embeds the agent name in the ``invoke_agent <name>`` span name from the
    start). The exporter then resolves the delegating agent against this index
    regardless of which batch each span exports in.

    Both dicts are bounded; the oldest entries are evicted once the cap is hit.
    """

    def __init__(self, max_entries: int = 8192) -> None:
        self._parent_by_span_id: dict[int, int] = {}
        self._agent_by_span_id: dict[int, str] = {}
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
        """Index a Pydantic AI span's parent link and (if an agent span) its name.

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
            if name.startswith(_INVOKE_AGENT_NAME_PREFIX):
                agent_name = name[len(_INVOKE_AGENT_NAME_PREFIX) :].strip()
                if agent_name:
                    self._evict_if_needed(self._agent_by_span_id)
                    self._agent_by_span_id[span_id] = agent_name
        except Exception:  # noqa: BLE001 - recording must never break tracing
            logger.debug("Failed to record span ancestry", exc_info=True)

    def find_ancestor_agent(self, span: ReadableSpan) -> str | None:
        """Resolve the nearest enclosing agent for a delegated span.

        Walks the persistent parent chain looking for an ``invoke_agent``
        ancestor. In Pydantic AI's delegation layout the chain is
        ``invoke_agent (child) -> execute_tool -> invoke_agent (parent)``, so
        the walk typically terminates in two hops.
        """
        cur_sid = self._span_id(span)
        # Bound the walk defensively against malformed parent cycles.
        for _ in range(64):
            if cur_sid is None:
                return None
            parent_sid = self._parent_by_span_id.get(cur_sid)
            if parent_sid is None:
                return None
            agent = self._agent_by_span_id.get(parent_sid)
            if agent is not None:
                return agent
            cur_sid = parent_sid
        return None


# Shared singleton: the dedup processor populates it at span start, the
# translating exporter reads it at export time. Both live in this module so a
# module-level instance is the simplest correct wiring.
_ancestry = _AncestryRegistry()


def _build_batch_lookups(
    spans: Sequence[ReadableSpan],
) -> tuple[dict[int, str], dict[int, ReadableSpan]]:
    """Index Pydantic AI spans in the batch by ``span_id`` for parent walks.

    Batch-local fallback for when the persistent registry has no entry (e.g.
    the integration was enabled with a processor that never saw ``on_start``).
    """
    agent_by_span_id: dict[int, str] = {}
    span_by_id: dict[int, ReadableSpan] = {}
    for span in spans:
        if not _is_pydantic_ai_span(span):
            continue
        ctx = getattr(span, "context", None)
        sid = getattr(ctx, "span_id", None)
        if sid is None:
            continue
        span_by_id[sid] = span
        attrs = span.attributes or {}
        if attrs.get(mapping.GEN_AI_OPERATION_NAME) == mapping.OP_INVOKE_AGENT:
            agent_name = attrs.get(mapping.GEN_AI_AGENT_NAME)
            if isinstance(agent_name, str) and agent_name:
                agent_by_span_id[sid] = agent_name
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
        parent_ctx = getattr(cur, "parent", None)
        parent_sid = getattr(parent_ctx, "span_id", None)
        if parent_sid is None:
            return None
        if parent_sid in agent_by_span_id:
            return agent_by_span_id[parent_sid]
        cur = span_by_id.get(parent_sid)
    return None


class PydanticAITranslatingExporter(SpanExporter):
    """Wrap any ``SpanExporter`` and rewrite Pydantic AI spans on their way out.

    Non-Pydantic-AI spans (LangChain, MAF, ``@observe``, ``@endpoint``, manual
    spans, ...) pass through untouched. Only spans whose instrumentation scope
    starts with ``"pydantic-ai"`` are translated.

    For every delegated agent run (an ``invoke_agent`` span whose ancestor
    chain contains a *different* agent), an ``ai.agent.handoff`` span is
    synthesized alongside the translated span, populating
    ``ai.agent.handoff.from`` / ``.to`` so multi-agent delegation renders with
    connected edges in the Rhesis Graph View.
    """

    def __init__(self, wrapped: SpanExporter) -> None:
        self._wrapped = wrapped

    @property
    def wrapped(self) -> SpanExporter:
        """The underlying exporter (e.g. ``RhesisOTLPExporter``)."""
        return self._wrapped

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        agent_by_span_id, span_by_id = _build_batch_lookups(spans)

        translated: list[ReadableSpan] = []
        for span in spans:
            if not _is_pydantic_ai_span(span):
                translated.append(span)
                continue

            try:
                translated_span = translate_span(span)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to translate Pydantic AI span %r; falling back to "
                    "function.pydantic_ai.* name so the backend still accepts it",
                    getattr(span, "name", "?"),
                    exc_info=True,
                )
                translated.append(_safe_fallback_span(span))
                continue
            translated.append(translated_span)

            # Handoff synthesis is best-effort and kept out of the try above:
            # a failure here must not fall back to re-translating the span,
            # which would duplicate the entry already appended above.
            try:
                raw_attrs = span.attributes or {}
                if raw_attrs.get(mapping.GEN_AI_OPERATION_NAME) == mapping.OP_INVOKE_AGENT:
                    to_agent = raw_attrs.get(mapping.GEN_AI_AGENT_NAME)
                    if isinstance(to_agent, str) and to_agent:
                        # Prefer the persistent registry (populated at span
                        # start, so it survives parent/child landing in
                        # different export batches); fall back to the
                        # batch-local parent walk.
                        from_agent = _ancestry.find_ancestor_agent(span)
                        if from_agent is None:
                            from_agent = _find_ancestor_agent_in_batch(
                                span, agent_by_span_id, span_by_id
                            )
                        if from_agent and from_agent != to_agent:
                            handoff = synthesize_handoff_span(span, from_agent, to_agent)
                            if handoff is not None:
                                translated.append(handoff)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to synthesize handoff span for Pydantic AI span %r",
                    getattr(span, "name", "?"),
                    exc_info=True,
                )
        return self._wrapped.export(translated)

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


class PydanticAILLMDedupSpanProcessor(SpanProcessor):
    """Span processor for ancestry recording and LLM-span deduplication.

    Two responsibilities, both requiring span *start* / *end* hooks (which the
    exporter wrapper does not get):

    1. Records every Pydantic AI span's parent link (and agent names from
       ``invoke_agent <name>`` span names) into the module-level
       :class:`_AncestryRegistry`, so the exporter can resolve handoff
       ``from`` agents across export batches.
    2. Toggles :func:`~rhesis.sdk.telemetry.context.is_llm_observation_active`
       for the duration of Pydantic AI ``chat`` spans so that any flag-checking
       auto-instrumentation running inside an agent run (e.g. the LangChain
       callback) skips emitting a duplicate ``ai.llm.invoke`` span.

    At ``on_start`` time Pydantic AI has not yet assigned attributes, so chat
    spans are detected from their name prefix (``"chat "``) and re-validated
    via the populated ``gen_ai.operation.name`` attribute in ``on_end``. The
    previous flag value is stashed keyed by span id (``on_end`` receives a
    different ``ReadableSpan`` snapshot object than ``on_start``).

    The processor exposes :meth:`activate` / :meth:`deactivate` so the
    integration's ``disable()`` can neutralize it without removing it from the
    ``TracerProvider`` (OTEL exposes no removal API).
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

    def _store_prev_flag(self, span, prev: bool) -> None:
        span_id = self._span_id(span)
        if span_id is None:
            return
        if len(self._prev_flags) >= self._PREV_FLAGS_MAX:
            try:
                first = next(iter(self._prev_flags))
                self._prev_flags.pop(first, None)
            except StopIteration:  # pragma: no cover - racy but harmless
                pass
        self._prev_flags[span_id] = prev

    def on_start(self, span, parent_context=None) -> None:  # noqa: D401
        if not self._active:
            return
        try:
            scope = getattr(span, "instrumentation_scope", None)
            scope_name = getattr(scope, "name", None)
            if not mapping.is_pydantic_ai_scope(scope_name):
                return
            # Record span ancestry for cross-batch handoff resolution. Done
            # for every Pydantic AI span (not just agent spans) so the parent
            # chain invoke_agent -> execute_tool -> invoke_agent is fully
            # indexed before any of them export.
            _ancestry.record(span)
            span_name = getattr(span, "name", "") or ""
            if not span_name.startswith("chat "):
                return
            prev = is_llm_observation_active()
            self._store_prev_flag(span, prev)
            if not prev:
                set_llm_observation_active(True)
        except Exception:  # noqa: BLE001 - on_start must never raise
            logger.debug("PydanticAILLMDedupSpanProcessor.on_start failed", exc_info=True)

    def on_end(self, span: ReadableSpan) -> None:
        if not self._active:
            return
        try:
            if not _is_pydantic_ai_span(span):
                return
            # Restore based on what on_start actually recorded rather than
            # re-deriving "is this a chat span" from attributes: if the
            # gen_ai.operation.name attribute were ever missing or renamed,
            # an attribute-gated restore would return early and leave the
            # flag stuck True for the rest of the context. _prev_flags only
            # contains entries for spans whose start hook toggled the flag,
            # so membership is the exact restore condition.
            span_id = self._span_id(span)
            if span_id is None or span_id not in self._prev_flags:
                return
            prev = bool(self._prev_flags.pop(span_id, False))
            if not prev:
                set_llm_observation_active(False)
        except Exception:  # noqa: BLE001 - on_end must never raise
            logger.debug("PydanticAILLMDedupSpanProcessor.on_end failed", exc_info=True)

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True
