"""OTel tracing event handler for agents.

Plug into any agent via ``event_handlers=[TracingHandler(...)]`` to get
automatic OpenTelemetry spans for every lifecycle stage without subclassing.
"""

import json
import logging
from typing import Any, Optional

from opentelemetry import context, trace

from rhesis.sdk.agents.events import AgentEventHandler

logger = logging.getLogger(__name__)


class TracingHandler(AgentEventHandler):
    """Adds Rhesis tracing spans to agent lifecycle events.

    Listens to the events already fired by BaseAgent and opens/closes
    OpenTelemetry spans around each stage.  No agent methods are overridden.

    Usage::

        from rhesis.sdk.agents.mcp import MCPAgent
        from rhesis.sdk.agents.tracing import TracingHandler

        agent = MCPAgent(
            model=model,
            mcp_client=client,
            event_handlers=[TracingHandler(model_name="gpt-4o")],
        )
    """

    def __init__(self, model_name: str = "unknown") -> None:
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
        span.end()
        context.detach(token)

    # ── agent lifecycle ─────────────────────────────────────────────

    async def on_agent_start(self, *, query: str, **kwargs: Any) -> None:
        self._open("agent", "function.mcp_agent_run")

    async def on_agent_end(self, *, result: Any, **kwargs: Any) -> None:
        # Drain any spans left open by mid-run errors
        for slot in ("llm", "tool", "iteration"):
            self._close(slot)
        self._close("agent", success=getattr(result, "success", True))

    # ── iteration lifecycle ─────────────────────────────────────────

    async def on_iteration_start(self, *, iteration: int, **kwargs: Any) -> None:
        self._open(
            "iteration",
            "function.mcp_agent_iteration",
            {"ai.agent.iteration": iteration},
        )

    async def on_iteration_end(self, *, iteration: int, action: str, **kwargs: Any) -> None:
        # The LLM span may still be open if _get_llm_action errored (on_error
        # fires instead of on_llm_end), so drain it here before closing the
        # iteration span.
        self._close("llm")
        self._close("tool")
        self._close("iteration", attributes={"ai.agent.action": action})

    # ── LLM lifecycle ───────────────────────────────────────────────

    async def on_llm_start(self, *, iteration: int, **kwargs: Any) -> None:
        self._open(
            "llm",
            "ai.llm.invoke",
            {
                "ai.operation.type": "llm.invoke",
                "ai.model.name": self._model_name,
                "ai.agent.iteration": iteration,
            },
        )

    async def on_llm_end(self, *, action: Any, **kwargs: Any) -> None:
        attrs: dict = {}
        if action is not None:
            attrs["ai.agent.reasoning"] = action.reasoning
            attrs["ai.agent.action"] = action.action
        self._close("llm", attributes=attrs)

    async def on_error(self, *, error: Exception, **kwargs: Any) -> None:
        # Close any open sub-operation span and record the error on it.
        # (BaseAgent emits on_error instead of on_llm_end when the LLM fails.)
        self._close("llm", exc=error)
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
