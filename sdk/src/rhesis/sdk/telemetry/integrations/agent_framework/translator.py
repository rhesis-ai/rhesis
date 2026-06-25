"""Span translator for Microsoft Agent Framework spans.

MAF emits spans natively in the OpenTelemetry GenAI semantic-convention shape.
The Rhesis backend expects spans in the ``ai.*`` / ``function.*`` schema.
Rather than hooking into a callback bus the way LangChain forces us to, we
let MAF emit its spans normally and translate them on their way out.

Architecture: the translator is implemented as a span-exporter wrapper. We
take the existing :class:`~rhesis.telemetry.exporter.RhesisOTLPExporter`
that's already attached to the shared
:class:`opentelemetry.sdk.trace.TracerProvider` and wrap it with
:class:`MAFTranslatingExporter`. Each batch of spans flows through the
wrapper exactly once: MAF spans are rewritten, every other span passes
through untouched. This avoids both double-exports and the need to
reconfigure samplers on an existing provider.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Iterable, Mapping, Sequence

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
from rhesis.sdk.telemetry.integrations.agent_framework import mapping

logger = logging.getLogger(__name__)

# Opt-out env var for span-noise reduction. When truthy, the translating
# exporter keeps MAF's low-value workflow infrastructure spans (edge-group /
# message-send routing primitives). By default they are dropped to keep
# fan-out topologies (e.g. ``HandoffBuilder`` broadcasts) readable.
_VERBOSE_WORKFLOW_SPANS_ENV = "RHESIS_MAF_VERBOSE_WORKFLOW_SPANS"

# Truthy string values for env vars.
_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})

# Shared id generator for synthesized handoff spans. OTel's TracerProvider
# doesn't expose its generator, so we use a fresh RandomIdGenerator; collisions
# with real span ids are astronomically unlikely (64-bit random).
_id_generator = RandomIdGenerator()


def _verbose_workflow_spans_enabled() -> bool:
    """Return whether low-value MAF workflow infra spans should be kept."""
    raw = os.getenv(_VERBOSE_WORKFLOW_SPANS_ENV)
    if raw is None:
        return False
    return raw.strip().lower() in _TRUTHY_ENV_VALUES


class _TranslatedSpan(ReadableSpan):
    """Read-only view that swaps the original span's name/attributes/events.

    OTEL ``ReadableSpan`` exposes its data via properties. By overriding only
    the three we care about we get a span that quacks like the original (kind,
    parent, status, timestamps, resource, instrumentation_scope, ...) but that
    appears in the Rhesis ``ai.*`` namespace to downstream consumers.
    """

    def __init__(
        self,
        original: ReadableSpan,
        new_name: str,
        new_attributes: Mapping[str, Any],
        new_events: Sequence[Event],
    ) -> None:
        # Skip ReadableSpan.__init__ on purpose: the parent stores fields in
        # private slots and forces us to copy them all over. Instead, we keep
        # the underlying span and forward unknown attribute access via
        # ``__getattr__`` below.
        self._original = original
        self._new_name = new_name
        self._new_attributes = dict(new_attributes)
        self._new_events = tuple(new_events)

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._new_name

    @property
    def attributes(self):  # type: ignore[override]
        return self._new_attributes

    @property
    def events(self):  # type: ignore[override]
        return self._new_events

    def __getattr__(self, item: str) -> Any:
        # __getattr__ is only consulted when normal lookup fails, so it never
        # masks the explicit overrides above.
        return getattr(self._original, item)

    def to_json(self, indent: int = 4) -> str:  # type: ignore[override]
        return self._original.to_json(indent=indent)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"_TranslatedSpan(name={self._new_name!r}, original={self._original!r})"


def _is_maf_span(span: ReadableSpan) -> bool:
    scope = getattr(span, "instrumentation_scope", None)
    scope_name = getattr(scope, "name", None)
    return mapping.is_maf_scope(scope_name)


def _translate_events(
    original_events: Iterable[Event],
    span_attributes: Mapping[str, Any],
) -> list[Event]:
    """Build the new event list, including synthesized tool I/O events."""
    new_events: list[Event] = []
    for event in original_events:
        new_name = mapping.translate_event_name(event.name)
        new_attrs = mapping.translate_event_attributes(event.name, event.attributes or {})
        new_events.append(Event(name=new_name, attributes=new_attrs, timestamp=event.timestamp))

    for synth_name, synth_attrs in mapping.synthesize_message_events(span_attributes):
        new_events.append(Event(name=synth_name, attributes=synth_attrs))

    for synth_name, synth_attrs in mapping.synthesize_tool_io_events(span_attributes):
        new_events.append(Event(name=synth_name, attributes=synth_attrs))

    return new_events


def translate_span(span: ReadableSpan) -> _TranslatedSpan:
    """Build the translated wrapper for a single MAF span.

    Pure function so it's trivially testable without an exporter.
    """
    raw_attrs = span.attributes or {}
    new_name = mapping.translate_span_name(span.name, raw_attrs)
    new_attrs = mapping.translate_attributes(raw_attrs)
    # When we land in the ``function.maf.*`` fallback (because MAF added a new
    # operation we don't map), preserve the original name as an attribute so
    # the trace remains debuggable downstream.
    if new_name.startswith("function.maf.") and span.name and span.name != new_name:
        new_attrs.setdefault("gen_ai.original_span_name", span.name)
    new_events = _translate_events(span.events or (), raw_attrs)
    return _TranslatedSpan(span, new_name, new_attrs, new_events)


def translate_handoff_span(
    span: ReadableSpan,
    from_agent: str | None,
) -> _TranslatedSpan:
    """Re-emit a MAF ``handoff_to_*`` tool span as an ``ai.agent.handoff`` span.

    Pure (modulo the ``ReadableSpan`` it returns). Caller is responsible for
    resolving ``from_agent`` from the OTel parent chain — see
    :meth:`MAFTranslatingExporter.export` for the resolution logic.

    Tool I/O events emitted by the original ``execute_tool`` span are kept
    as-is. They are still meaningful (the model's chosen handoff arguments
    typically include the message text it routed to the target agent).
    """
    raw_attrs = span.attributes or {}
    new_attrs = mapping.translate_handoff_attributes(raw_attrs, from_agent=from_agent)
    new_events = _translate_events(span.events or (), raw_attrs)
    return _TranslatedSpan(span, "ai.agent.handoff", new_attrs, new_events)


def synthesize_handoff_spans(
    chat_span: ReadableSpan,
    from_agent: str | None,
    targets: Sequence[str],
) -> list[ReadableSpan]:
    """Build ``ai.agent.handoff`` spans for handoffs found in a chat span.

    MAF's ``HandoffBuilder`` never emits ``execute_tool handoff_to_*`` spans
    (the middleware short-circuits the tool before its span is created), so the
    only observable record of a handoff is the assistant ``tool_call`` part in
    the chat span's ``gen_ai.output.messages``. This helper turns each such
    handoff into a fresh ``ai.agent.handoff`` span that the Rhesis Graph View
    can use to draw the agent-to-agent edge.

    Each synthesized span:

    - gets a brand-new ``span_id`` (so it does not collide with real spans),
    - shares the chat span's ``trace_id`` and is parented to the chat span's
      parent (the enclosing ``invoke_agent`` span), making it a sibling of the
      chat span and a child of the calling agent in the trace tree,
    - is zero-duration at the chat span's end time,
    - carries ``ai.operation.type = agent.handoff`` plus
      ``ai.agent.handoff.to`` (always) and ``ai.agent.handoff.from`` (when the
      calling agent could be resolved).

    Returns an empty list when there are no targets or the chat span lacks a
    usable span context.
    """
    if not targets:
        return []

    ctx = getattr(chat_span, "context", None)
    trace_id = getattr(ctx, "trace_id", None)
    if trace_id is None:
        return []

    trace_flags = getattr(ctx, "trace_flags", None) or TraceFlags(TraceFlags.SAMPLED)
    parent = getattr(chat_span, "parent", None)
    end_time = getattr(chat_span, "end_time", None)
    resource = getattr(chat_span, "resource", None)
    scope = getattr(chat_span, "instrumentation_scope", None)

    synthesized: list[ReadableSpan] = []
    for target in targets:
        attrs: dict[str, Any] = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_AGENT_HANDOFF,
            AIAttributes.AGENT_HANDOFF_TO: target,
        }
        if from_agent:
            attrs[AIAttributes.AGENT_HANDOFF_FROM] = from_agent

        new_ctx = SpanContext(
            trace_id=trace_id,
            span_id=_id_generator.generate_span_id(),
            is_remote=False,
            trace_flags=trace_flags,
        )
        synthesized.append(
            ReadableSpan(
                name="ai.agent.handoff",
                context=new_ctx,
                parent=parent,
                resource=resource,
                attributes=attrs,
                events=(),
                kind=SpanKind.INTERNAL,
                instrumentation_scope=scope,
                status=Status(StatusCode.OK),
                start_time=end_time,
                end_time=end_time,
            )
        )
    return synthesized


def _safe_fallback_span(span: ReadableSpan) -> ReadableSpan:
    """Build the safest possible wrapper when :func:`translate_span` raises.

    The raw MAF span name (e.g. ``"chat gpt-4"``) fails the Rhesis
    backend's :func:`~rhesis.sdk.telemetry.attributes.validate_span_name`
    regex, so simply forwarding the original span on a translation error
    causes silent HTTP 422 drops. Funnel the span into ``function.maf.*``
    instead so the backend accepts it. The original name is stashed as
    ``gen_ai.original_span_name`` for downstream debugging, alongside whatever
    raw attributes the original span carried.
    """
    original_name = getattr(span, "name", None) or ""
    fallback_name = mapping.fallback_function_maf_name(original_name)
    raw_attrs = dict(span.attributes or {})
    if original_name and original_name != fallback_name:
        raw_attrs.setdefault("gen_ai.original_span_name", original_name)
    raw_events = tuple(span.events or ())
    try:
        return _TranslatedSpan(span, fallback_name, raw_attrs, raw_events)
    except Exception:  # noqa: BLE001 - the wrapper itself must never raise
        logger.debug(
            "Failed to build fallback _TranslatedSpan; forwarding original",
            exc_info=True,
        )
        return span


def _build_maf_batch_lookups(
    spans: Sequence[ReadableSpan],
) -> tuple[dict[int, str], dict[int, ReadableSpan]]:
    """Index MAF spans in the batch by ``span_id`` for parent-chain walks.

    Returns:
        ``(agent_by_span_id, span_by_id)`` where:

        - ``agent_by_span_id`` maps an ``invoke_agent`` span's id to its
          ``gen_ai.agent.name`` value.
        - ``span_by_id`` maps every MAF span's id to the span itself so the
          parent-chain walker can hop across intermediate non-agent spans
          (the ``chat`` span typically sits between the agent and the tool).
    """
    agent_by_span_id: dict[int, str] = {}
    span_by_id: dict[int, ReadableSpan] = {}
    # Agent name indexed by the agent span's parent id, so a sibling chat span
    # (same parent) can resolve its caller — see _HandoffAncestryRegistry for
    # why the sibling layout matters in MAF's HandoffBuilder workflows.
    agent_by_parent_span_id: dict[int, str] = {}
    for span in spans:
        if not _is_maf_span(span):
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
                parent_ctx = getattr(span, "parent", None)
                parent_sid = getattr(parent_ctx, "span_id", None)
                if parent_sid is not None:
                    agent_by_parent_span_id[parent_sid] = agent_name
    return agent_by_span_id, span_by_id, agent_by_parent_span_id


def _find_ancestor_agent_in_batch(
    span: ReadableSpan,
    *,
    agent_by_span_id: dict[int, str],
    span_by_id: dict[int, ReadableSpan],
    agent_by_parent_span_id: dict[int, str] | None = None,
) -> str | None:
    """Walk the OTel parent chain to find the calling ``invoke_agent`` span.

    At each hop we check both the classic nested layout (an ancestor
    ``invoke_agent`` span) and the sibling layout used by MAF's
    ``HandoffBuilder`` (an ``invoke_agent`` span sharing the current parent
    ``executor.process`` span). ``None`` when the chain runs out (e.g. the
    agent span was exported in an earlier batch). The bounded loop guard
    guarantees termination even in the face of a malformed parent cycle.
    """
    agent_by_parent_span_id = agent_by_parent_span_id or {}
    cur: ReadableSpan | None = span
    # Bound the walk defensively. Real MAF trees are at most a handful of
    # levels deep (workflow -> executor -> agent -> chat -> tool), so 32 is
    # generous; the guard exists purely to make a malformed cycle survivable.
    for _ in range(32):
        if cur is None:
            return None
        parent_ctx = getattr(cur, "parent", None)
        parent_sid = getattr(parent_ctx, "span_id", None)
        if parent_sid is None:
            return None
        if parent_sid in agent_by_span_id:
            return agent_by_span_id[parent_sid]
        if parent_sid in agent_by_parent_span_id:
            return agent_by_parent_span_id[parent_sid]
        cur = span_by_id.get(parent_sid)
    return None


_INVOKE_AGENT_NAME_PREFIX = "invoke_agent "


class _HandoffAncestryRegistry:
    """Persistent (process-lifetime) span ancestry index for handoff edges.

    The batch-local lookup in :func:`_find_ancestor_agent_in_batch` fails when
    a handoff tool span and its enclosing ``invoke_agent`` span are exported in
    different batches. That is the common case under ``BatchSpanProcessor``:
    a child span ends (and is enqueued) *before* its parent, so on long runs
    the agent ancestor lands in a later batch than the tool span that needs it.

    This registry sidesteps batching entirely by recording ancestry at span
    *start* time (a parent always starts before its children, and MAF embeds
    the agent name in the ``invoke_agent <name>`` span name from the start).
    The exporter then resolves ``from_agent`` against this index regardless of
    which batch each span exports in.

    Both dicts are bounded; the oldest entries are evicted once the cap is hit.
    """

    def __init__(self, max_entries: int = 8192) -> None:
        self._parent_by_span_id: dict[int, int] = {}
        self._agent_by_span_id: dict[int, str] = {}
        # Agent name indexed by its *parent* span id. MAF's workflow path does
        # not always nest the chat span under the ``invoke_agent`` span: in
        # ``HandoffBuilder`` runs the ``invoke_agent`` span and the ``chat``
        # span are SIBLINGS sharing the same ``executor.process`` parent. The
        # parent-chain walk alone can't see the agent in that layout, so we also
        # remember "this parent owns agent X" to resolve handoffs from sibling
        # chat spans.
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
        """Index a MAF span's parent link and (if an agent span) its name.

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
                    if parent_sid is not None:
                        self._evict_if_needed(self._agent_by_parent_span_id)
                        self._agent_by_parent_span_id[parent_sid] = agent_name
        except Exception:  # noqa: BLE001 - recording must never break tracing
            logger.debug("Failed to record span ancestry", exc_info=True)

    def find_ancestor_agent(self, span: ReadableSpan) -> str | None:
        """Resolve the calling agent for a handoff/chat span.

        Walks the persistent parent chain and, at each hop, checks two ways the
        agent name may be reachable:

        1. an ancestor ``invoke_agent`` span (the classic nested layout, e.g.
           tool -> chat -> invoke_agent), and
        2. a *sibling* ``invoke_agent`` span sharing the current parent (MAF's
           ``HandoffBuilder`` layout, where chat and invoke_agent are both
           children of the same ``executor.process`` span).
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
            # Sibling layout: an invoke_agent span shares this parent.
            sibling_agent = self._agent_by_parent_span_id.get(parent_sid)
            if sibling_agent is not None:
                return sibling_agent
            cur_sid = parent_sid
        return None


# Shared singleton: the dedup processor populates it at span start, the
# translating exporter reads it at export time. Both live in this module so a
# module-level instance is the simplest correct wiring.
_handoff_ancestry = _HandoffAncestryRegistry()


class MAFTranslatingExporter(SpanExporter):
    """Wrap any ``SpanExporter`` and rewrite MAF spans on their way out.

    Non-MAF spans (LangChain, ``@observe``, ``@endpoint``, manual spans, ...)
    pass through untouched. Only spans whose instrumentation scope starts with
    ``"agent_framework"`` are translated.

    Agent-to-agent handoffs are reconstructed two ways:

    1. Primary (current MAF): MAF's ``HandoffBuilder`` short-circuits
       ``handoff_to_*`` tool calls via middleware, so they never produce an
       ``execute_tool`` span. The handoff is only visible as an assistant
       ``tool_call`` part in the chat span's ``gen_ai.output.messages``. For
       each such chat span we synthesize a fresh ``ai.agent.handoff`` span
       (see :func:`synthesize_handoff_spans`).
    2. Fallback (older MAF / other patterns): if an ``execute_tool
       handoff_to_<target>`` span ever is emitted, it is re-named to
       ``ai.agent.handoff`` directly.

    Both paths populate ``ai.agent.handoff.from`` / ``.to``, which is what
    makes multi-agent workflows render with connected coordinator->specialist
    edges in the Rhesis Graph View.

    To keep fan-out topologies readable, low-value MAF workflow infrastructure
    spans (edge-group / message-send routing primitives) are dropped by
    default; pass ``verbose_workflow_spans=True`` (or set
    ``RHESIS_MAF_VERBOSE_WORKFLOW_SPANS``) to keep them.
    """

    def __init__(
        self,
        wrapped: SpanExporter,
        *,
        verbose_workflow_spans: bool | None = None,
    ) -> None:
        self._wrapped = wrapped
        self._verbose_workflow_spans = (
            _verbose_workflow_spans_enabled()
            if verbose_workflow_spans is None
            else verbose_workflow_spans
        )

    @property
    def wrapped(self) -> SpanExporter:
        """The underlying exporter (e.g. ``RhesisOTLPExporter``)."""
        return self._wrapped

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        # Build batch-local lookups so we can resolve the originating agent
        # for ``handoff_to_*`` tool spans. MAF emits the calling agent as an
        # ``invoke_agent <name>`` ancestor of the tool span; we record one
        # entry per MAF span here so the per-handoff resolver can walk the
        # OTel parent chain inside this batch.
        agent_by_span_id, span_by_id, agent_by_parent_span_id = _build_maf_batch_lookups(spans)

        translated: list[ReadableSpan] = []
        for span in spans:
            if _is_maf_span(span):
                # Drop low-value workflow infrastructure spans (edge-group /
                # message-send) unless the caller opted into verbose output.
                if not self._verbose_workflow_spans and mapping.is_low_value_workflow_span(
                    getattr(span, "name", None)
                ):
                    continue
                try:
                    raw_attrs = span.attributes or {}
                    if mapping.is_handoff_tool_span(raw_attrs):
                        # Prefer the persistent registry (populated at span
                        # start, so it survives parent/child landing in
                        # different export batches); fall back to the
                        # batch-local parent walk.
                        from_agent = _handoff_ancestry.find_ancestor_agent(span)
                        if from_agent is None:
                            from_agent = _find_ancestor_agent_in_batch(
                                span,
                                agent_by_span_id=agent_by_span_id,
                                span_by_id=span_by_id,
                                agent_by_parent_span_id=agent_by_parent_span_id,
                            )
                        translated.append(translate_handoff_span(span, from_agent))
                    else:
                        translated.append(translate_span(span))
                        # Synthesize ai.agent.handoff spans from handoff tool
                        # calls recorded in this chat span's output messages.
                        # This is the primary handoff path for current MAF,
                        # where HandoffBuilder short-circuits the tool and no
                        # execute_tool span is emitted.
                        targets = mapping.extract_handoff_targets_from_messages(raw_attrs)
                        if targets:
                            from_agent = _handoff_ancestry.find_ancestor_agent(span)
                            if from_agent is None:
                                from_agent = _find_ancestor_agent_in_batch(
                                    span,
                                    agent_by_span_id=agent_by_span_id,
                                    span_by_id=span_by_id,
                                    agent_by_parent_span_id=agent_by_parent_span_id,
                                )
                            translated.extend(synthesize_handoff_spans(span, from_agent, targets))
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "Failed to translate MAF span %r; falling back to "
                        "function.maf.* name so the backend still accepts it",
                        getattr(span, "name", "?"),
                        exc_info=True,
                    )
                    translated.append(_safe_fallback_span(span))
            else:
                translated.append(span)
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


class MAFLLMDedupSpanProcessor(SpanProcessor):
    """Span processor that toggles the LLM-observation flag for MAF chat spans.

    What this dedups (and what it does NOT):

    * Toggles
      :func:`~rhesis.sdk.telemetry.context.is_llm_observation_active` for the
      duration of MAF ``chat`` spans so that any **flag-checking
      auto-instrumentation running inside an MAF agent** skips emitting a
      duplicate ``ai.llm.invoke`` span. The LangChain callback is the canonical
      consumer of that flag, see
      :mod:`rhesis.sdk.telemetry.integrations.langchain.callback`.
    * It does **not** dedup ``@observe.llm`` against MAF.
      :func:`~rhesis.sdk.decorators.observe.ObserveDecorator.llm` only **sets**
      the flag, it never reads it; consequently wrapping an MAF call with
      ``@observe.llm`` will produce two ``ai.llm.invoke`` spans (one from the
      decorator, one from the translated MAF span). True dedup of that case
      requires teaching ``@observe.llm`` to consult the flag, which is a
      separate, broader change.

    The flag is a context variable, so it correctly scopes to the current
    async/thread context. ``on_end`` restores the flag to its previous value
    (captured by ``on_start``) so an outer scope that pre-set the flag (e.g.
    an enclosing ``@observe.llm``) is not clobbered.

    This is a separate processor (rather than embedded in the exporter wrapper)
    because the toggle must happen at span *start* / *end*, not at export time.

    The processor exposes :meth:`activate` / :meth:`deactivate` so the
    integration's ``disable()`` can neutralize the processor without removing
    it from the ``TracerProvider`` (OTEL exposes no removal API). When the
    processor is inactive, all hooks short-circuit and never touch the flag.
    """

    def __init__(self) -> None:
        self._active = False
        # Storage for the previous-flag value, keyed by ``span_context.span_id``.
        #
        # We learned the hard way that sidecar attributes on the Span object
        # are NOT a viable storage mechanism: ``on_start`` receives a writable
        # ``_Span`` and ``on_end`` receives a different ``ReadableSpan``
        # snapshot built from it (verified empirically against
        # ``opentelemetry-sdk`` 1.x). Anything stashed via ``setattr`` on the
        # ``_Span`` is invisible to the snapshot. We therefore always
        # round-trip through this dict and clear entries in ``on_end``.
        # The cap is a defensive guard against pathological cases where
        # ``on_end`` never runs; in normal use the dict shrinks to empty.
        self._prev_flags: dict[int, bool] = {}
        self._PREV_FLAGS_MAX = 4096

    def activate(self) -> None:
        """Mark the processor active so ``on_start``/``on_end`` toggle the flag."""
        self._active = True

    def deactivate(self) -> None:
        """Mark the processor inactive; subsequent hooks are no-ops.

        Used by :meth:`MAFIntegration.disable` because OTEL's TracerProvider
        does not let us remove an already-registered span processor.
        """
        self._active = False
        # Drop pending fallback entries so they don't leak across an
        # enable/disable cycle.
        self._prev_flags.clear()

    @staticmethod
    def _span_id(span) -> int | None:
        """Return ``span_context.span_id`` if present, else ``None``."""
        ctx = getattr(span, "context", None)
        if ctx is None:
            try:
                ctx = span.get_span_context()  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                return None
        return getattr(ctx, "span_id", None)

    def _store_prev_flag(self, span, prev: bool) -> None:
        """Stash the outer flag value where ``on_end`` can find it.

        Keyed by ``span_context.span_id`` because OTEL's
        ``SynchronousMultiSpanProcessor`` re-builds a ``ReadableSpan``
        snapshot for ``on_end`` (different object identity than the
        writable ``_Span`` the start hook received) — sidecar attributes on
        the writable span are not visible to that snapshot.
        """
        span_id = self._span_id(span)
        if span_id is None:
            return
        if len(self._prev_flags) >= self._PREV_FLAGS_MAX:
            # Defensive eviction: drop the oldest entry (insertion order in
            # Python 3.7+ dicts) rather than grow without bound.
            try:
                first = next(iter(self._prev_flags))
                self._prev_flags.pop(first, None)
            except StopIteration:  # pragma: no cover - racy but harmless
                pass
        self._prev_flags[span_id] = prev

    def _retrieve_prev_flag(self, span) -> bool:
        """Read back the flag value stashed by :meth:`_store_prev_flag`.

        Pops the entry to keep the dict bounded across long-running runs.
        ``False`` is returned when the span_id was never stashed (e.g.
        because the on_start hook saw the span before our chat-name check
        recognized it).
        """
        span_id = self._span_id(span)
        if span_id is None:
            return False
        return bool(self._prev_flags.pop(span_id, False))

    def on_start(self, span, parent_context=None) -> None:  # noqa: D401
        if not self._active:
            return
        try:
            scope = getattr(span, "instrumentation_scope", None)
            scope_name = getattr(scope, "name", None)
            if not mapping.is_maf_scope(scope_name):
                return
            # Record span ancestry for cross-batch handoff ``from_agent``
            # resolution. Done for every MAF span (not just chat spans) so the
            # parent chain tool -> chat -> invoke_agent is fully indexed before
            # any of them export.
            _handoff_ancestry.record(span)
            # NOTE: at ``on_start`` time MAF has not yet called
            # ``span.set_attributes(...)``. ``ChatTelemetryLayer`` constructs
            # the span via ``start_span(f"{operation} {span_name}")`` and only
            # *then* assigns attributes. We therefore detect chat spans from
            # their **name prefix** (``"chat "``) here, and re-validate via
            # the populated ``gen_ai.operation.name`` attribute in
            # :meth:`on_end`. Without this the previous-flag value was never
            # stashed, and ``on_end`` would silently clobber any outer
            # ``@observe.llm`` scope.
            span_name = getattr(span, "name", "") or ""
            if not span_name.startswith("chat "):
                return
            prev = is_llm_observation_active()
            self._store_prev_flag(span, prev)
            if not prev:
                set_llm_observation_active(True)
        except Exception:  # noqa: BLE001 - on_start must never raise
            logger.debug("MAFLLMDedupSpanProcessor.on_start failed", exc_info=True)

    def on_end(self, span: ReadableSpan) -> None:
        if not self._active:
            return
        try:
            if not _is_maf_span(span):
                return
            attrs = span.attributes or {}
            if attrs.get(mapping.GEN_AI_OPERATION_NAME) != mapping.OP_CHAT:
                return
            prev = self._retrieve_prev_flag(span)
            if not prev:
                set_llm_observation_active(False)
        except Exception:  # noqa: BLE001 - on_end must never raise
            logger.debug("MAFLLMDedupSpanProcessor.on_end failed", exc_info=True)

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True
