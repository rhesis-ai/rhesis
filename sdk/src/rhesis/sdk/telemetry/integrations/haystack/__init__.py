"""Haystack framework integration for Rhesis observability.

Haystack emits native OpenTelemetry spans (``haystack.pipeline.run``,
``haystack.component.run``). This integration enables Haystack tracing, turns
on content capture, and wraps the active Rhesis exporter with
:class:`~rhesis.sdk.telemetry.integrations.haystack.translator.HaystackTranslatingExporter`
so spans reach the backend in the ``ai.*`` schema.

Usage::

    from rhesis.sdk import RhesisClient
    from rhesis.sdk.telemetry import auto_instrument

    client = RhesisClient(api_key=..., project_id=...)
    auto_instrument("haystack")

Installation::

    pip install "rhesis-sdk[haystack]"

Important: create the ``RhesisClient`` (which configures the global
``TracerProvider`` and ``RhesisOTLPExporter``) *before* calling
``auto_instrument("haystack")``. If no Rhesis tracer provider is active,
``enable()`` returns ``False`` and Haystack spans are not translated.
"""

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
