"""OTel tracing event handler for agents.

Plug into any agent via ``event_handlers=[TracingHandler(...)]`` to get
automatic OpenTelemetry spans for every lifecycle stage without subclassing.
"""

import json
import logging
from typing import Any, Optional

from opentelemetry import context, trace

from rhesis.sdk.agents.events import AgentEventHandler
from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents
from rhesis.telemetry.schemas import AIOperationType

logger = logging.getLogger(__name__)

# Cap input/output content stamped on agent spans to keep the OTEL
# exporter payload small.  Mirrors the langchain integration cap.
_MAX_AGENT_CONTENT = 8000


class TracingHandler(AgentEventHandler):
    """Adds Rhesis tracing spans to agent lifecycle events.

    Listens to the events already fired by BaseAgent and opens/closes
    OpenTelemetry spans around each stage.  No agent methods are overridden.

    The agent-level span follows the OTEL semantic convention used by
    the langchain integration: ``ai.agent.invoke`` with ``ai.agent.name``,
    ``ai.operation.type`` and ``ai.agent.input`` / ``ai.agent.output``
    events.  This keeps multi-agent traces consistent regardless of which
    integration produced them.

    Usage::

        from rhesis.sdk.agents.mcp import MCPAgent
        from rhesis.sdk.agents.tracing import TracingHandler

        agent = MCPAgent(
            model=model,
            mcp_client=client,
            event_handlers=[TracingHandler(
                agent_name="research-agent",
                model_name="gpt-4o",
            )],
        )
    """

    def __init__(
        self,
        agent_name: str = "agent",
        model_name: str = "unknown",
    ) -> None:
        self._agent_name = agent_name
        self._model_name = model_name
        # slot_name → (span, context_token)
        self._slots: dict[str, tuple] = {}

    # ── internal helpers ────────────────────────────────────────────

    def _get_tracer(self) -> Optional[trace.Tracer]:
        try:
            from rhesis.sdk.decorators._state import get_default_client, is_client_disabled

            if is_client_disabled():
                return None
            client = get_default_client()
            return client._tracer.tracer if client else None
        except Exception:
            return None

    def _open(self, slot: str, span_name: str, attributes: dict | None = None) -> None:
        """Start a named span and attach it to the current OTel context."""
        t = self._get_tracer()
        if t is None:
            return
        span = t.start_span(span_name, kind=trace.SpanKind.INTERNAL)
        if attributes:
            for k, v in attributes.items():
                try:
                    span.set_attribute(k, v)
                except Exception:
                    pass
        token = context.attach(trace.set_span_in_context(span))
        self._slots[slot] = (span, token)

    def _close(
        self,
        slot: str,
        attributes: dict | None = None,
        success: bool = True,
        exc: Exception | None = None,
    ) -> None:
        """End a named span. No-op if the slot was never opened."""
        entry = self._slots.pop(slot, None)
        if entry is None:
            return
        span, token = entry
        if attributes:
            for k, v in attributes.items():
                try:
                    span.set_attribute(k, v)
                except Exception:
                    pass
        if exc:
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
        elif success:
            span.set_status(trace.Status(trace.StatusCode.OK))
        else:
            # Agent reported failure without raising (e.g.
            # ``AgentResult(success=False, error=...)``).  Mark the
            # span as ERROR so the viewer still surfaces the failure;
            # ``ai.error.type`` is expected to be stamped by the
            # caller via ``attributes``.
            span.set_status(trace.Status(trace.StatusCode.ERROR))
        span.end()
        context.detach(token)

    # ── agent lifecycle ─────────────────────────────────────────────

    async def on_agent_start(self, *, query: str, **kwargs: Any) -> None:
        """Open the agent-level ``ai.agent.invoke`` span.

        Mirrors the langchain integration's agent span shape so the
        rhesis viewer treats single-agent (MCP/architect) runs and
        multi-agent (langgraph) runs uniformly.
        """
        self._open(
            "agent",
            AIOperationType.AGENT_INVOKE,
            attributes={
                AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_AGENT_INVOKE,
                AIAttributes.AGENT_NAME: self._agent_name,
                AIAttributes.MODEL_NAME: self._model_name,
            },
        )
        # Stamp the user query as a span event so the input is captured
        # without bloating the attribute payload.
        entry = self._slots.get("agent")
        if entry and query:
            span = entry[0]
            span.add_event(
                AIEvents.AGENT_INPUT,
                {AIAttributes.AGENT_INPUT_CONTENT: str(query)[:_MAX_AGENT_CONTENT]},
            )

    async def on_agent_end(self, *, result: Any, **kwargs: Any) -> None:
        # Drain any spans left open by mid-run errors
        for slot in ("tool", "iteration"):
            self._close(slot)
        # Capture the final answer as an ``ai.agent.output`` event
        # before ending the agent span.
        entry = self._slots.get("agent")
        if entry:
            span = entry[0]
            final_answer = getattr(result, "final_answer", None)
            if final_answer:
                span.add_event(
                    AIEvents.AGENT_OUTPUT,
                    {AIAttributes.AGENT_OUTPUT_CONTENT: str(final_answer)[:_MAX_AGENT_CONTENT]},
                )
            error = getattr(result, "error", None)
            if error:
                span.set_attribute(AIAttributes.ERROR_TYPE, "agent_failure")
        self._close("agent", success=getattr(result, "success", True))

    # ── iteration lifecycle ─────────────────────────────────────────

    async def on_iteration_start(self, *, iteration: int, **kwargs: Any) -> None:
        self._open(
            "iteration",
            "function.mcp_agent_iteration",
            {"ai.agent.iteration": iteration},
        )

    async def on_iteration_end(self, *, iteration: int, action: str, **kwargs: Any) -> None:
        self._close("tool")
        self._close("iteration", attributes={"ai.agent.action": action})

    async def on_error(self, *, error: Exception, **kwargs: Any) -> None:
        # Close any open tool span and record the error on it.
        self._close("tool", exc=error)

    # ── tool lifecycle ──────────────────────────────────────────────

    async def on_tool_start(
        self,
        *,
        tool_name: str,
        arguments: dict,
        **kwargs: Any,
    ) -> None:
        attrs: dict = {
            "ai.operation.type": "tool.invoke",
            "ai.tool.name": tool_name,
        }
        if arguments:
            try:
                attrs["ai.tool.arguments"] = json.dumps(arguments)
            except Exception:
                pass
        self._open("tool", "ai.tool.invoke", attrs)

    async def on_tool_end(self, *, tool_name: str, result: Any, **kwargs: Any) -> None:
        attrs: dict = {"ai.tool.success": result.success}
        if result.success:
            attrs["ai.tool.output"] = result.content
        else:
            attrs["ai.tool.error"] = result.error or "Unknown error"
        self._close("tool", attributes=attrs, success=result.success)
