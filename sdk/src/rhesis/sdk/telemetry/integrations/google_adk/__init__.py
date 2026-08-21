"""Google ADK integration package.

This package provides OpenTelemetry-based tracing for Google ADK (Agent
Development Kit) applications:

- Agent activations (``ai.agent.invoke``) with ``ai.agent.name``
- Model calls (``ai.llm.invoke``) with model, provider, token counts, finish
  reason, and ``ai.prompt`` / ``ai.completion`` events carrying real text
- Tool calls (``ai.tool.invoke``) with ``ai.tool.input`` / ``ai.tool.output``
- Agent-to-agent handoffs (``ai.agent.handoff``) for **both** ADK multi-agent
  mechanisms -- ``sub_agents`` + ``transfer_to_agent`` and ``AgentTool`` -- so the
  Rhesis Graph View renders connected edges
- Workflows, nodes and the run root (``function.google_adk.*``)
- Conversation turn roots, and every turn of a conversation joined into one
  trace rather than one trace per turn -- both without any manual span code

ADK emits OTEL spans natively under the instrumentation scope
``gcp.vertex.agent``; this integration translates them into Rhesis's ``ai.*`` /
``function.*`` schema before they reach the backend. Both ADK telemetry schema
versions (``ADK_TELEMETRY_SCHEMA_VERSION_OPT_IN`` = ``1`` or ``2``) are
supported, and neither is forced.

Usage::

    from rhesis.sdk import RhesisClient
    from rhesis.sdk.telemetry import auto_instrument

    client = RhesisClient(api_key=..., project_id=...)
    auto_instrument("google_adk")   # or the "adk" alias

Installation
------------

Install the optional ``google-adk`` extra::

    pip install "rhesis-sdk[google-adk]"

Ordering matters
----------------

Create ``RhesisClient`` **before** calling ``auto_instrument``. The client is
what installs Rhesis's ``TracerProvider``, and this integration works by
wrapping the exporter already attached to it. With no Rhesis provider in place
there is nothing to wrap, so ``enable()`` returns ``False`` and logs a warning
rather than silently letting untranslated spans reach the backend, where they
would be rejected with HTTP 422.

Things worth knowing
--------------------

.. warning::

    Do **not** call ``google.adk.telemetry.setup.maybe_set_otel_providers()``.
    It installs its own ``TracerProvider`` / ``LoggerProvider`` /
    ``MeterProvider``, replacing the ones Rhesis configured, and your spans stop
    reaching the Rhesis backend.

**Use ``run_async``, not ``run``.** ``Runner.run`` executes the agent on a fresh
thread, which gets fresh context variables. That means the ADK spans start a new
trace instead of nesting under an enclosing Rhesis ``@endpoint`` / ``@observe``
span, and the conversation id set via ``rhesis.telemetry.context`` is invisible
to them. ``Runner.run_async`` (and ``run_debug``) nest correctly.

**Conversation joining needs the id set before the run.** ADK opens its own run
root per turn and OTEL mints a fresh trace id for it, so the integration rewrites
the turn's spans onto a trace id shared by the conversation. That target has to be
known when the run span is *created*, and ADK assigns no span attributes until much
later, so the only readable source is
``rhesis.telemetry.context.set_conversation_id``. Without one, the ADK session id
still labels the turn root -- that is read at export -- but the turns stay on
separate traces. The rewrite only ever applies to a standalone run: when
``root_trace_id`` or ``conversation_trace_id`` is set, Rhesis owns the trace id,
publishes it onwards and writes its own turn records to it, so the ids are left
untouched. The conversation's first turn is never moved either.

**ADK cannot be turned off.** Unlike MAF and Pydantic AI, ADK has no
instrumentation switch -- it emits spans as soon as any ``TracerProvider``
exists. ``disable()`` therefore unwraps the exporters and deactivates the span
processor, but ADK keeps emitting; those spans then pass through untranslated,
exactly as if the integration had never been enabled.

**Content capture** is on by default, sourced from ADK's own span attributes.
Set ``RHESIS_DISABLE_CONTENT_CAPTURE`` to a truthy value to switch it off; the
integration then forces ADK's three content knobs, including
``ADK_TELEMETRY_IGNORE_RUN_CONFIG`` so a per-request ``RunConfig.telemetry``
cannot put prompts back. ``OTEL_SEMCONV_STABILITY_OPT_IN`` is never touched --
it is a global OpenTelemetry switch affecting unrelated instrumentation.

**``google-adk[otel-gcp]`` is not needed and not supported.** That extra installs
``opentelemetry-instrumentation-google-genai``, which makes ADK hand the model
span to a different instrumentation scope. Traces stay complete either way
(``call_llm`` is still ADK's own and still becomes ``ai.llm.invoke``), but the
other library's spans are not translated.

**Verbose spans.** ADK infrastructure spans (``send_data``, ``create_cache``,
``handle_context_caching``, ``compact_events``, ``execute_tool (merged)``) are
dropped by default. Set ``RHESIS_GOOGLE_ADK_VERBOSE_SPANS`` to a truthy value to
forward them under ``function.google_adk.*``.
"""

from rhesis.sdk.telemetry.integrations.google_adk.integration import (
    GoogleADKIntegration,
    get_integration,
)
from rhesis.sdk.telemetry.integrations.google_adk.translator import (
    GoogleADKLLMDedupSpanProcessor,
    GoogleADKTranslatingExporter,
    conversation_root_attributes,
    synthesize_handoff_span,
    translate_handoff_span,
    translate_span,
    verbose_spans_enabled,
)

__all__ = [
    "GoogleADKIntegration",
    "GoogleADKLLMDedupSpanProcessor",
    "GoogleADKTranslatingExporter",
    "conversation_root_attributes",
    "get_integration",
    "synthesize_handoff_span",
    "translate_handoff_span",
    "translate_span",
    "verbose_spans_enabled",
]
