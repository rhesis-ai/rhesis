"""Span translator for Haystack native OpenTelemetry spans."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping, Sequence

from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from rhesis.sdk.telemetry.integrations.genai import TranslatedSpan
from rhesis.sdk.telemetry.integrations.haystack import mapping

logger = logging.getLogger(__name__)


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
        new_events.append(
            Event(name=event.name, attributes=dict(event.attributes or {}), timestamp=event.timestamp)
        )

    existing_names = {event.name for event in new_events}
    for synth_name, synth_attrs in mapping.synthesize_events(attributes, span_name=span_name):
        if synth_name in existing_names:
            continue
        new_events.append(Event(name=synth_name, attributes=synth_attrs, timestamp=0))
        existing_names.add(synth_name)

    return new_events


def translate_span(span: ReadableSpan) -> TranslatedSpan:
    """Build the translated wrapper for a single Haystack span."""
    raw_attrs = span.attributes or {}
    original_name = span.name or ""
    new_name = mapping.translate_span_name(original_name, raw_attrs)
    new_attrs = mapping.translate_attributes(raw_attrs, span_name=original_name)
    if new_name.startswith("function.haystack.") and original_name and original_name != new_name:
        new_attrs.setdefault("haystack.original_span_name", original_name)
    new_events = _translate_events(span.events or (), new_attrs, span_name=original_name)
    return TranslatedSpan(span, new_name, new_attrs, new_events)


def _safe_fallback_span(span: ReadableSpan) -> ReadableSpan:
    original_name = getattr(span, "name", None) or ""
    fallback_name = mapping.fallback_function_haystack_name(original_name)
    raw_attrs = dict(span.attributes or {})
    if original_name and original_name != fallback_name:
        raw_attrs.setdefault("haystack.original_span_name", original_name)
    raw_events = tuple(span.events or ())
    try:
        return TranslatedSpan(span, fallback_name, raw_attrs, raw_events)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to build fallback TranslatedSpan; forwarding original", exc_info=True)
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
