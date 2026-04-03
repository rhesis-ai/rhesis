"""Lightweight OpenTelemetry telemetry for the Rhesis platform."""

from rhesis.telemetry.exporter import RhesisOTLPExporter
from rhesis.telemetry.provider import get_tracer_provider, shutdown_tracer_provider
from rhesis.telemetry.schemas import (
    OTELSpan,
    OTELTraceBatch,
    SpanEvent,
    SpanKind,
    SpanLink,
    StatusCode,
)

__all__ = [
    "RhesisOTLPExporter",
    "get_tracer_provider",
    "shutdown_tracer_provider",
    "OTELSpan",
    "OTELTraceBatch",
    "SpanEvent",
    "SpanKind",
    "SpanLink",
    "StatusCode",
]
