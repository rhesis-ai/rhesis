"""ArchitectAgent -- conversational agent for building test suites.

Tools are injected by the caller. The agent is agnostic to whether
tools call backend services directly or connect via MCP over HTTP.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import jinja2

from rhesis.sdk.agents.base import BaseAgent, BaseTool, MCPTool
from rhesis.sdk.agents.events import AgentEventHandler, _emit
from rhesis.sdk.agents.schemas import (
    AgentAction,
    ExecutionStep,
    ToolCall,
    ToolResult,
)
from rhesis.sdk.models.base import BaseLLM

from .plan import ArchitectPlan

logger = logging.getLogger(__name__)

# Valid mode transitions
_MODE_ORDER = [
    "discovery",
    "planning",
    "creating",
    "execution",
    "complete",
]


class ArchitectAgent:
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
        verbose: bool = False,
        event_handlers: Optional[List[AgentEventHandler]] = None,
    ):
        self._model = BaseAgent._resolve_model(model)
        self._tools: List[Union[BaseTool, MCPTool]] = list(tools or [])
        self._max_iterations = max_iterations
        self._verbose = verbose
        self._event_handlers: List[AgentEventHandler] = list(event_handlers or [])

        self._conversation_history: List[Dict[str, Any]] = []
        self._execution_history: List[ExecutionStep] = []
        self._plan: Optional[ArchitectPlan] = None
        self._mode: str = "discovery"

        # Template environment
        templates_dir = Path(__file__).parent / "prompt_templates"
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._system_prompt = self._load_system_prompt()

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
        self._conversation_history.append({"role": "user", "content": message})

        if self._verbose:
            print(f"\n[Architect:{self._mode}] User: {message}")

        await _emit(self._event_handlers, "on_agent_start", query=message)

        try:
            # Run the internal ReAct loop for this turn
            response = await self._run_turn(message)

            self._conversation_history.append({"role": "assistant", "content": response})

            if self._verbose:
                print(f"[Architect:{self._mode}] Response: {response[:200]}...")

            return response
        finally:
            # Disconnect MCP tools before asyncio.run() destroys the
            # event loop, preventing orphaned async generators.
            await self._disconnect_tools()

    @property
    def plan(self) -> Optional[ArchitectPlan]:
        """The current plan, if one has been produced."""
        return self._plan

    @plan.setter
    def plan(self, value: ArchitectPlan) -> None:
        """Set the plan and emit a plan_update event."""
        self._plan = value
        # Fire-and-forget is not ideal, but plan is set from sync
        # context. Callers using async should use set_plan_async().

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

    # ── tool aggregation ────────────────────────────────────────────

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Aggregate tool descriptions from all sources."""
        all_tools: List[Dict[str, Any]] = []
        for tool in self._tools:
            if isinstance(tool, MCPTool):
                all_tools.extend(await tool.list_tools())
            elif isinstance(tool, BaseTool):
                all_tools.append(tool.to_dict())
        return all_tools

    # ── internal ReAct loop (per turn) ──────────────────────────────

    async def _run_turn(self, user_message: str) -> str:
        """Run the ReAct loop for a single conversation turn."""
        available_tools = await self.get_available_tools()
        iteration = 0

        while iteration < self._max_iterations:
            iteration += 1

            if self._verbose:
                print(f"  [turn iteration {iteration}/{self._max_iterations}]")

            await _emit(self._event_handlers, "on_iteration_start", iteration=iteration)

            prompt = self._build_turn_prompt(user_message, available_tools)
            action = await self._get_llm_action(prompt, iteration)

            if action is None:
                await _emit(
                    self._event_handlers,
                    "on_iteration_end",
                    iteration=iteration,
                    action="error",
                )
                return "I encountered an error processing your request. Please try again."

            if self._verbose:
                print(f"  Reasoning: {action.reasoning[:120]}...")
                print(f"  Action: {action.action}")

            if action.action == "finish":
                await _emit(
                    self._event_handlers,
                    "on_iteration_end",
                    iteration=iteration,
                    action="finish",
                )
                return action.final_answer or ""

            if action.action == "call_tool" and action.tool_calls:
                results = await self._execute_tool_calls(action.tool_calls)
                step = ExecutionStep(
                    iteration=iteration,
                    reasoning=action.reasoning,
                    action="call_tool",
                    tool_calls=action.tool_calls,
                    tool_results=results,
                )
                self._execution_history.append(step)

            await _emit(
                self._event_handlers,
                "on_iteration_end",
                iteration=iteration,
                action=action.action,
            )

        return (
            "I've reached the maximum number of internal "
            "iterations for this turn. Please send another "
            "message to continue."
        )

    # ── tool execution ──────────────────────────────────────────────

    async def _execute_tool_calls(
        self,
        tool_calls: List[ToolCall],
    ) -> List[ToolResult]:
        """Execute tool calls by routing to the correct tool source."""
        results: List[ToolResult] = []

        for tc in tool_calls:
            arguments = tc.arguments if isinstance(tc.arguments, dict) else {}
            await _emit(
                self._event_handlers,
                "on_tool_start",
                tool_name=tc.tool_name,
                arguments=arguments,
            )

            result = await self._execute_single_tool(tc)
            results.append(result)

            await _emit(
                self._event_handlers,
                "on_tool_end",
                tool_name=tc.tool_name,
                result=result,
            )

            if self._verbose:
                if result.success:
                    print(f"    + {result.tool_name}: {len(result.content)} chars")
                else:
                    print(f"    x {result.tool_name}: {result.error}")

        return results

    async def _execute_single_tool(self, tool_call: ToolCall) -> ToolResult:
        """Route a tool call to the matching tool source."""
        tool_name = tool_call.tool_name
        arguments = tool_call.arguments if isinstance(tool_call.arguments, dict) else {}

        for tool in self._tools:
            if isinstance(tool, BaseTool):
                if tool.name == tool_name:
                    try:
                        return await tool.execute(**arguments)
                    except Exception as e:
                        return ToolResult(
                            tool_name=tool_name,
                            success=False,
                            error=str(e),
                        )
            elif isinstance(tool, MCPTool):
                # MCPTool hosts multiple tools; try execution
                try:
                    return await tool.execute(tool_name, **arguments)
                except Exception as e:
                    # Tool might not be from this MCP server;
                    # if it's a "tool not found" error, continue
                    error_str = str(e).lower()
                    if "not found" in error_str:
                        continue
                    return ToolResult(
                        tool_name=tool_name,
                        success=False,
                        error=str(e),
                    )

        return ToolResult(
            tool_name=tool_name,
            success=False,
            error=f"Tool '{tool_name}' not found",
        )

    # ── prompt building ─────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        template = self._jinja_env.get_template("system_prompt.j2")
        return template.render()

    def _build_turn_prompt(
        self,
        user_message: str,
        available_tools: List[Dict[str, Any]],
    ) -> str:
        tools_text = self._format_tools(available_tools)
        history_text = self._format_history()
        plan_text = self._plan.to_markdown() if self._plan else ""

        template = self._jinja_env.get_template("iteration_prompt.j2")
        return template.render(
            mode=self._mode,
            user_query=user_message,
            tools_text=tools_text,
            history_text=history_text,
            plan_text=plan_text,
        )

    def _format_tools(self, tools: List[Dict[str, Any]]) -> str:
        if not tools:
            return "(no tools available)"
        descriptions = []
        for tool in tools:
            desc = f"- {tool['name']}: {tool.get('description', 'No description')}"
            if "inputSchema" in tool and tool["inputSchema"]:
                schema = tool["inputSchema"]
                if "properties" in schema:
                    params = ", ".join(schema["properties"].keys())
                    desc += f"\n  Parameters: {params}"
            descriptions.append(desc)
        return "\n".join(descriptions)

    def _format_history(self) -> str:
        parts: List[str] = []

        # Conversation history
        for msg in self._conversation_history:
            role = msg["role"].capitalize()
            content = msg["content"]
            if len(content) > 500:
                content = content[:500] + "..."
            parts.append(f"{role}: {content}")

        # Execution history (tool calls/results)
        for step in self._execution_history:
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

    # ── LLM interaction ─────────────────────────────────────────────

    async def _get_llm_action(self, prompt: str, iteration: int) -> Optional[AgentAction]:
        """Get the LLM's structured action decision."""
        await _emit(self._event_handlers, "on_llm_start", iteration=iteration)

        try:
            response = self._model.generate(
                prompt=prompt,
                system_prompt=self._system_prompt,
                schema=AgentAction,
            )
            if isinstance(response, dict):
                action = AgentAction(**response)
            else:
                action = AgentAction(**json.loads(response))

            await _emit(self._event_handlers, "on_llm_end", action=action)
            return action
        except Exception as e:
            logger.error(
                f"[Architect] Failed to parse LLM response: {e}",
                exc_info=True,
            )
            await _emit(self._event_handlers, "on_error", error=e)
            return None
