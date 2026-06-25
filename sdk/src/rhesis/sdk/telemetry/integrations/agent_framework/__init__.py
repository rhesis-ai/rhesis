"""Microsoft Agent Framework integration package.

This package provides OpenTelemetry-based tracing for Microsoft Agent
Framework (MAF) operations including:

- Agent invocations (``ai.agent.invoke``)
- LLM/chat invocations (``ai.llm.invoke``) with token usage and provider
- Tool/function executions (``ai.tool.invoke``)
- Embedding generation (``ai.embedding.generate``)
- Workflow runs (``function.workflow.*``)

MAF emits OTEL spans natively in the GenAI semantic-convention shape; this
integration translates them into Rhesis's ``ai.*`` / ``function.*`` schema
before they reach the backend.

Usage::

    from rhesis.sdk import RhesisClient
    from rhesis.sdk.telemetry import auto_instrument

    client = RhesisClient(api_key=..., project_id=...)
    auto_instrument("agent_framework")

Installation
------------

Install the optional ``agent-framework`` extra::

    pip install "rhesis-sdk[agent-framework]"

The extra pins the individual MAF subpackages
(``agent-framework-core``, ``agent-framework-openai``,
``agent-framework-orchestrations``) rather than the ``agent-framework``
meta-package.

.. warning::

    Do **not** ``pip install agent-framework`` (the meta-package) into
    the same environment. The meta-package transitively pulls
    ``agent-framework-azure-ai-search==0.0.0a1``, a placeholder
    distribution that ships an *empty* ``agent_framework/__init__.py``;
    depending on install order it can clobber the real ``__init__.py``
    from ``agent-framework-core`` and break every ``from agent_framework
    import ...`` statement. ``MAFIntegration.is_installed()`` detects
    this case by also importing ``agent_framework.observability`` and
    will report the integration as not installed when the clobber
    happens.

Important: do **not** call
``agent_framework.observability.configure_otel_providers()`` after creating
``RhesisClient`` -- that would replace Rhesis's ``TracerProvider`` and your
spans would no longer reach the Rhesis backend.
"""

from rhesis.sdk.telemetry.integrations.agent_framework.integration import (
    MAFIntegration,
    get_integration,
)
from rhesis.sdk.telemetry.integrations.agent_framework.translator import (
    MAFLLMDedupSpanProcessor,
    MAFTranslatingExporter,
    translate_handoff_span,
    translate_span,
)

__all__ = [
    "MAFIntegration",
    "MAFLLMDedupSpanProcessor",
    "MAFTranslatingExporter",
    "get_integration",
    "translate_handoff_span",
    "translate_span",
]
