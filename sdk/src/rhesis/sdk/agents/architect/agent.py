"""ArchitectAgent -- conversational agent for building test suites.

Extends BaseAgent with multi-turn conversation, mode management, and
plan tracking. Tools are injected by the caller.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rhesis.sdk.agents.base import BaseAgent, BaseTool, MCPTool
from rhesis.sdk.agents.events import AgentEventHandler, _emit
from rhesis.sdk.models.base import BaseLLM

from .plan import ArchitectPlan

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """Conversational agent for designing and creating test suites.

    Maintains state across conversation turns. Tools are injected
    by the caller -- the agent doesn't know or care whether they
    call backend services directly or go through MCP over HTTP.

    Supports ``event_handlers`` for real-time lifecycle notifications
    (tool execution, mode changes, plan updates, etc.).

    Usage::

        architect = ArchitectAgent(
            model="vertex_ai/gemini-2.0-flash",
            tools=[*get_rhesis_tools(), extra_tool],
            event_handlers=[WebSocketHandler(ws.send_json)],
        )
        response = architect.chat("I need tests for a chatbot")
        response = architect.chat("Focus on safety and fairness")
        response = architect.chat("Looks good, create everything")
    """

    def __init__(
        self,
        model: Optional[Union[str, BaseLLM]] = None,
        tools: Optional[List[Union[BaseTool, MCPTool]]] = None,
        max_iterations: int = 15,
        max_tool_executions: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        history_window: Optional[int] = None,
        verbose: bool = False,
        event_handlers: Optional[List[AgentEventHandler]] = None,
    ):
        super().__init__(
            model=model,
            tools=tools,
            max_iterations=max_iterations,
            max_tool_executions=max_tool_executions,
            timeout_seconds=timeout_seconds,
            history_window=history_window,
            verbose=verbose,
            event_handlers=event_handlers,
            prompt_templates_dir=(Path(__file__).parent / "prompt_templates"),
        )
        self._conversation_history: List[Dict[str, Any]] = []
        self._plan: Optional[ArchitectPlan] = None
        self._mode: str = "discovery"

    # ── public API ──────────────────────────────────────────────────

    def chat(self, message: str) -> str:
        """Send a message and get a response.

        This is the main conversational interface. Each call is
        one turn in the conversation. The agent may call tools
        internally before responding.

        Args:
            message: User's message text.

        Returns:
            The agent's response text.
        """
        return asyncio.run(self.chat_async(message))

    async def chat_async(self, message: str) -> str:
        """Async version of chat()."""
        async with self._turn_lock:
            self._conversation_history.append({"role": "user", "content": message})

            if self.verbose:
                print(f"\n[Architect:{self._mode}] User: {message}")

            await _emit(
                self._event_handlers,
                "on_agent_start",
                query=message,
            )

            try:
                response = await self._run_loop(message)

                self._conversation_history.append({"role": "assistant", "content": response})

                if self.verbose:
                    print(f"[Architect:{self._mode}] Response: {response[:200]}...")

                return response
            finally:
                await self._disconnect_tools()

    @property
    def plan(self) -> Optional[ArchitectPlan]:
        """The current plan, if one has been produced."""
        return self._plan

    @plan.setter
    def plan(self, value: ArchitectPlan) -> None:
        """Set the plan and emit a plan_update event."""
        self._plan = value

    async def set_plan_async(self, value: ArchitectPlan) -> None:
        """Set the plan and emit a plan_update event (async)."""
        self._plan = value
        await _emit(self._event_handlers, "on_plan_update", plan=value)

    @property
    def mode(self) -> str:
        """Current agent mode."""
        return self._mode

    async def set_mode_async(self, new_mode: str) -> None:
        """Transition to a new mode and emit an event."""
        old_mode = self._mode
        if old_mode != new_mode:
            self._mode = new_mode
            await _emit(
                self._event_handlers,
                "on_mode_change",
                old_mode=old_mode,
                new_mode=new_mode,
            )

    def reset(self) -> None:
        """Reset all state for a fresh conversation."""
        self._conversation_history.clear()
        self._execution_history.clear()
        self._plan = None
        self._mode = "discovery"

    # ── transport lifecycle ─────────────────────────────────────────

    async def _disconnect_tools(self) -> None:
        """Disconnect all MCP tool transports.

        Called at the end of each ``chat_async()`` turn so that the
        transport's async generators are properly closed before
        ``asyncio.run()`` destroys the event loop. The auto-reconnect
        in ``MCPTool._ensure_connected()`` handles the next call.
        """
        for tool in self._tools:
            if isinstance(tool, MCPTool):
                try:
                    await tool.disconnect()
                except Exception:
                    pass

    # ── prompt building (overrides) ────────────────────────────────

    def _build_prompt(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
    ) -> str:
        tools_text = self._format_tools(available_tools)
        history_text = self._format_history()
        plan_text = self._plan.to_markdown() if self._plan else ""

        template = self._jinja_env.get_template("iteration_prompt.j2")
        return template.render(
            mode=self._mode,
            user_query=user_query,
            tools_text=tools_text,
            history_text=history_text,
            plan_text=plan_text,
        )

    def _format_history(self) -> str:
        parts: List[str] = []

        # Conversation history -- windowed
        conv_window = self._conversation_history[-self._history_window :]
        if len(self._conversation_history) > self._history_window:
            omitted = len(self._conversation_history) - self._history_window
            parts.append(f"[... {omitted} earlier messages omitted ...]")
        for msg in conv_window:
            role = msg["role"].capitalize()
            content = msg["content"]
            if len(content) > 500:
                content = content[:500] + "..."
            parts.append(f"{role}: {content}")

        # Execution history -- windowed
        exec_window = self._execution_history[-self._history_window :]
        if len(self._execution_history) > self._history_window:
            omitted = len(self._execution_history) - self._history_window
            parts.append(f"[... {omitted} earlier tool steps omitted ...]")
        for step in exec_window:
            parts.append(f"[Tool iteration {step.iteration}] Reasoning: {step.reasoning[:200]}")
            if step.tool_calls:
                for tc in step.tool_calls:
                    parts.append(f"  Called: {tc.tool_name}")
            if step.tool_results:
                for tr in step.tool_results:
                    if tr.success:
                        content_preview = tr.content[:300]
                        parts.append(f"  Result ({tr.tool_name}): {content_preview}")
                    else:
                        parts.append(f"  Error ({tr.tool_name}): {tr.error}")

        return "\n".join(parts) if parts else ""
