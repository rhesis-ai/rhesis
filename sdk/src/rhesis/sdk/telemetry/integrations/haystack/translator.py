"""Span translator for Haystack native OpenTelemetry spans."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping, Sequence

from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from rhesis.sdk.telemetry.integrations.haystack import mapping

logger = logging.getLogger(__name__)


class _TranslatedSpan(ReadableSpan):
    """Read-only view that swaps the original span's name/attributes/events."""

    def __init__(
        self,
        original: ReadableSpan,
        new_name: str,
        new_attributes: Mapping[str, Any],
        new_events: Sequence[Event],
    ) -> None:
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
        return getattr(self._original, item)

    def to_json(self, indent: int = 4) -> str:  # type: ignore[override]
        return self._original.to_json(indent=indent)

    def __repr__(self) -> str:  # pragma: no cover
        return f"_TranslatedSpan(name={self._new_name!r}, original={self._original!r})"


def _is_haystack_span(span: ReadableSpan) -> bool:
    scope = getattr(span, "instrumentation_scope", None)
    scope_name = getattr(scope, "name", None)
    if mapping.is_haystack_scope(scope_name):
        return True
    return mapping.is_haystack_span_name(getattr(span, "name", None))


def _translate_events(
    original_events: Iterable[Event],
    attributes: Mapping[str, Any],
    *,
    span_name: str,
) -> list[Event]:
    new_events: list[Event] = []
    for event in original_events:
        new_events.append(Event(name=event.name, attributes=dict(event.attributes or {}), timestamp=event.timestamp))

    existing_names = {event.name for event in new_events}
    for synth_name, synth_attrs in mapping.synthesize_events(attributes, span_name=span_name):
        if synth_name in existing_names:
            continue
        new_events.append(Event(name=synth_name, attributes=synth_attrs, timestamp=0))
        existing_names.add(synth_name)

    return new_events


def translate_span(span: ReadableSpan) -> _TranslatedSpan:
    """Build the translated wrapper for a single Haystack span."""
    raw_attrs = span.attributes or {}
    original_name = span.name or ""
    new_name = mapping.translate_span_name(original_name, raw_attrs)
    new_attrs = mapping.translate_attributes(raw_attrs, span_name=original_name)
    if new_name.startswith("function.haystack.") and original_name and original_name != new_name:
        new_attrs.setdefault("haystack.original_span_name", original_name)
    new_events = _translate_events(span.events or (), new_attrs, span_name=original_name)
    return _TranslatedSpan(span, new_name, new_attrs, new_events)


def _safe_fallback_span(span: ReadableSpan) -> ReadableSpan:
    original_name = getattr(span, "name", None) or ""
    fallback_name = mapping.fallback_function_haystack_name(original_name)
    raw_attrs = dict(span.attributes or {})
    if original_name and original_name != fallback_name:
        raw_attrs.setdefault("haystack.original_span_name", original_name)
    raw_events = tuple(span.events or ())
    try:
        return _TranslatedSpan(span, fallback_name, raw_attrs, raw_events)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to build fallback _TranslatedSpan; forwarding original", exc_info=True)
        return span


class HaystackTranslatingExporter(SpanExporter):
    """Wrap any ``SpanExporter`` and rewrite Haystack spans on their way out."""

    def __init__(self, wrapped: SpanExporter) -> None:
        self._wrapped = wrapped

    @property
    def wrapped(self) -> SpanExporter:
        return self._wrapped

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        translated: list[ReadableSpan] = []
        for span in spans:
            if _is_haystack_span(span):
                try:
                    translated.append(translate_span(span))
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "Failed to translate Haystack span %r; falling back to function.haystack.*",
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
