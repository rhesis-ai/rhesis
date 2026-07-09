"""Pydantic AI integration package.

This package provides OpenTelemetry-based tracing for Pydantic AI operations
including:

- Agent runs (``ai.agent.invoke``) via ``run()``, ``run_sync()``, and
  ``run_stream()``
- LLM/chat invocations (``ai.llm.invoke``) with token usage, provider, and
  message events
- Tool executions (``ai.tool.invoke``) with input/output events
- Multi-agent delegation (``ai.agent.handoff``) with from/to agent edges

Pydantic AI ships built-in OpenTelemetry instrumentation that emits spans in
the GenAI semantic-convention shape; this integration enables it (pinned to a
known instrumentation version, with binary content excluded) and translates
the spans into Rhesis's ``ai.*`` schema before they reach the backend. This
replaces the previous approach of monkey-patching ``Agent.run``, which could
not see model calls, tool executions, streaming runs, or delegation.

Usage::

    from rhesis.sdk import RhesisClient
    from rhesis.sdk.telemetry import auto_instrument

    client = RhesisClient(api_key=..., project_id=...)
    auto_instrument("pydantic_ai")

Installation
------------

Install the optional ``pydantic-ai`` extra::

    pip install "rhesis-sdk[pydantic-ai]"

Important: create the ``RhesisClient`` (which configures the global
``TracerProvider``) *before* calling ``auto_instrument()``, and do not
configure Logfire's own OTel providers on top — that would replace Rhesis's
``TracerProvider`` and your spans would no longer reach the Rhesis backend.
"""

from rhesis.sdk.telemetry.integrations.pydantic_ai.integration import (
    PINNED_INSTRUMENTATION_VERSION,
    PydanticAIIntegration,
    get_integration,
)
from rhesis.sdk.telemetry.integrations.pydantic_ai.translator import (
    PydanticAILLMDedupSpanProcessor,
    PydanticAITranslatingExporter,
    synthesize_handoff_span,
    translate_span,
)

__all__ = [
    "PINNED_INSTRUMENTATION_VERSION",
    "PydanticAIIntegration",
    "PydanticAILLMDedupSpanProcessor",
    "PydanticAITranslatingExporter",
    "get_integration",
    "synthesize_handoff_span",
    "translate_span",
]
