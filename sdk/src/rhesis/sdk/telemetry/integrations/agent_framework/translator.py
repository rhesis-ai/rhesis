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
from typing import Any, Iterable, Mapping, Sequence

from opentelemetry.sdk.trace import Event, ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from rhesis.sdk.telemetry.context import (
    is_llm_observation_active,
    set_llm_observation_active,
)
from rhesis.sdk.telemetry.integrations.agent_framework import mapping

logger = logging.getLogger(__name__)


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


class MAFTranslatingExporter(SpanExporter):
    """Wrap any ``SpanExporter`` and rewrite MAF spans on their way out.

    Non-MAF spans (LangChain, ``@observe``, ``@endpoint``, manual spans, ...)
    pass through untouched. Only spans whose instrumentation scope starts with
    ``"agent_framework"`` are translated.
    """

    def __init__(self, wrapped: SpanExporter) -> None:
        self._wrapped = wrapped

    @property
    def wrapped(self) -> SpanExporter:
        """The underlying exporter (e.g. ``RhesisOTLPExporter``)."""
        return self._wrapped

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        translated: list[ReadableSpan] = []
        for span in spans:
            if _is_maf_span(span):
                try:
                    translated.append(translate_span(span))
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
