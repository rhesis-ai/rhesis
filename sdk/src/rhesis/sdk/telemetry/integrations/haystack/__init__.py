"""Haystack framework integration for Rhesis observability."""

from rhesis.sdk.telemetry.integrations.haystack.integration import (
    HaystackIntegration,
    HaystackPatchState,
    get_integration,
)
from rhesis.sdk.telemetry.integrations.haystack.mapping import (
    fallback_function_haystack_name,
    is_haystack_scope,
    is_haystack_span_name,
    synthesize_events,
    translate_attributes,
    translate_span_name,
)
from rhesis.sdk.telemetry.integrations.haystack.translator import (
    HaystackTranslatingExporter,
    translate_span,
)

__all__ = [
    "HaystackIntegration",
    "HaystackPatchState",
    "HaystackTranslatingExporter",
    "fallback_function_haystack_name",
    "get_integration",
    "is_haystack_scope",
    "is_haystack_span_name",
    "synthesize_events",
    "translate_attributes",
    "translate_span",
    "translate_span_name",
]
