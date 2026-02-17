"""Event handler interface for agent lifecycle notifications.

Agents emit events at key lifecycle points. Handlers receive these
events and can forward them to websockets, logging, telemetry, etc.

All handler methods are no-ops by default so subclasses only need to
override the events they care about.

Usage::

    class WebSocketHandler(AgentEventHandler):
        def __init__(self, send_fn):
            self._send = send_fn

        async def on_tool_start(self, *, tool_name, arguments, **kw):
            await self._send({"type": "tool_start", "tool": tool_name})

    architect = ArchitectAgent(
        model="vertex_ai/gemini-2.0-flash",
        tools=[...],
        event_handlers=[WebSocketHandler(ws.send_json)],
    )
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from rhesis.sdk.agents.architect.plan import ArchitectPlan
    from rhesis.sdk.agents.schemas import AgentAction, AgentResult, ToolResult

logger = logging.getLogger(__name__)


class AgentEventHandler:
    """Base class for receiving agent lifecycle events.

    All methods are async no-ops by default. Override only the
    events you want to handle. Handlers should never raise --
    exceptions are caught and logged so one broken handler cannot
    disrupt the agent.
    """

    # ── agent lifecycle ─────────────────────────────────────────────

    async def on_agent_start(self, *, query: str, **kwargs: Any) -> None:
        """Called when the agent begins processing a query."""

    async def on_agent_end(self, *, result: "AgentResult", **kwargs: Any) -> None:
        """Called when the agent finishes (success or failure)."""

    async def on_error(self, *, error: Exception, **kwargs: Any) -> None:
        """Called when the agent encounters an unrecoverable error."""

    # ── iteration lifecycle ─────────────────────────────────────────

    async def on_iteration_start(self, *, iteration: int, **kwargs: Any) -> None:
        """Called at the start of each ReAct iteration."""

    async def on_iteration_end(self, *, iteration: int, action: str, **kwargs: Any) -> None:
        """Called at the end of each ReAct iteration."""

    # ── LLM lifecycle ───────────────────────────────────────────────

    async def on_llm_start(self, *, iteration: int, **kwargs: Any) -> None:
        """Called before the LLM is invoked."""

    async def on_llm_end(self, *, action: "AgentAction", **kwargs: Any) -> None:
        """Called after the LLM responds with a parsed action."""

    # ── tool lifecycle ──────────────────────────────────────────────

    async def on_tool_start(
        self, *, tool_name: str, arguments: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Called before a tool is executed."""

    async def on_tool_end(self, *, tool_name: str, result: "ToolResult", **kwargs: Any) -> None:
        """Called after a tool finishes (success or failure)."""

    # ── architect-specific ──────────────────────────────────────────

    async def on_mode_change(self, *, old_mode: str, new_mode: str, **kwargs: Any) -> None:
        """Called when the ArchitectAgent transitions between modes."""

    async def on_plan_update(self, *, plan: "ArchitectPlan", **kwargs: Any) -> None:
        """Called when the ArchitectAgent updates its plan."""


async def _emit(
    handlers: List[AgentEventHandler],
    event: str,
    **kwargs: Any,
) -> None:
    """Dispatch an event to all registered handlers.

    Exceptions from individual handlers are caught and logged so
    a broken handler never disrupts the agent's execution.
    """
    for handler in handlers:
        method = getattr(handler, event, None)
        if method is None:
            continue
        try:
            await method(**kwargs)
        except Exception:
            logger.exception(
                "Event handler %s.%s failed",
                type(handler).__name__,
                event,
            )
