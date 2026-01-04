"""Telemetry background tasks."""

from rhesis.backend.tasks.telemetry.enrich import enrich_trace_async

__all__ = ["enrich_trace_async"]
