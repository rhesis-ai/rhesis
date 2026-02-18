"""Base classes for agents and tools.

BaseAgent provides the ReAct loop. BaseTool is the abstract tool interface.
MCPTool adapts MCP servers into the BaseTool interface.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import jinja2

from rhesis.sdk.agents.events import AgentEventHandler, _emit
from rhesis.sdk.agents.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolCall,
    ToolResult,
)
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger(__name__)


# ── BaseTool ────────────────────────────────────────────────────────


class BaseTool(ABC):
    """Abstract base class for tools that agents can invoke.

    Subclass this to create concrete tools. Both SDK-side and
    backend-side tools share this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name identifying this tool."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        ...

    @property
    def parameters_schema(self) -> dict:
        """JSON Schema describing accepted parameters."""
        return {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute this tool with the given arguments."""
        ...

    def to_dict(self) -> dict:
        """Serialize tool metadata for LLM tool descriptions."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters_schema,
        }


# ── MCPTool ─────────────────────────────────────────────────────────


class MCPTool:
    """Wraps an MCP server as a tool source for agents.

    MCPTool is not a single tool -- it represents a *server* that
    exposes multiple tools via the MCP protocol. Agents expand it
    into individual tool descriptions at runtime.
    """

    def __init__(self, client):
        self._client = client
        self._connected = False

    @classmethod
    def from_url(
        cls,
        url: str,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> "MCPTool":
        """Connect to an MCP server via HTTP/StreamableHTTP."""
        from rhesis.sdk.agents.mcp.client import MCPClient

        final_headers = dict(headers or {})
        if api_key:
            final_headers["Authorization"] = f"Bearer {api_key}"

        client = MCPClient(
            server_name="http",
            transport_type="http",
            transport_params={"url": url, "headers": final_headers},
        )
        return cls(client=client)

    @classmethod
    def from_provider(
        cls,
        provider: str,
        credentials: Dict[str, str],
    ) -> "MCPTool":
        """Connect to a known MCP provider (confluence, jira, etc.).

        Uses built-in provider templates to configure the connection.
        """
        from rhesis.sdk.agents.mcp.client import MCPClientFactory

        factory = MCPClientFactory.from_provider(provider, credentials)
        # Get the server name from the config
        config = factory._load_config()
        servers = config.get("mcpServers", {})
        server_name = next(iter(servers))
        client = factory.create_client(server_name)
        return cls(client=client)

    async def _ensure_connected(self) -> None:
        """Connect or reconnect if the session was lost."""
        if not self._connected:
            await self.connect()
            return
        # Session may have been destroyed (e.g. event loop closed
        # between asyncio.run() calls). Detect and reconnect.
        session = getattr(self._client, "session", None)
        if session is None:
            self._connected = False
            await self.connect()

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Discover tools from the MCP server."""
        try:
            await self._ensure_connected()
            return await self._client.list_tools()
        except Exception:
            # Reconnect on any transport error
            self._connected = False
            await self.connect()
            return await self._client.list_tools()

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Route execution to the MCP server."""
        try:
            await self._ensure_connected()
        except Exception:
            self._connected = False
            await self.connect()

        result = await self._client.call_tool(tool_name, kwargs)

        # Extract content from MCP result
        content_parts = []
        content_list = getattr(result, "content", None)
        if content_list:
            for item in content_list:
                if hasattr(item, "text"):
                    content_parts.append(item.text)
                elif hasattr(item, "resource"):
                    resource = item.resource
                    if hasattr(resource, "text"):
                        content_parts.append(resource.text)
        content = "\n\n".join(content_parts)

        # Check for MCP-level errors
        if hasattr(result, "isError") and result.isError:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                content="",
                error=content,
            )

        return ToolResult(tool_name=tool_name, success=True, content=content)

    async def connect(self) -> None:
        """Connect to the MCP server."""
        await self._client.connect()
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        await self._client.disconnect()
        self._connected = False


# ── BaseAgent ───────────────────────────────────────────────────────


class BaseAgent(ABC):
    """Abstract base class providing the ReAct reasoning loop.

    Subclasses must implement:
      - get_available_tools()  -- return tool descriptions
      - execute_tool()         -- dispatch a ToolCall

    Supports event handlers for lifecycle notifications (tool start/end,
    LLM invocations, iteration progress, etc.). Pass a list of
    ``AgentEventHandler`` instances to receive events.
    """

    def __init__(
        self,
        model: Optional[Union[str, BaseLLM]] = None,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10,
        verbose: bool = False,
        prompt_templates_dir: Optional[Path] = None,
        event_handlers: Optional[List[AgentEventHandler]] = None,
    ):
        # Template environment
        templates_dir = prompt_templates_dir or (Path(__file__).parent / "mcp" / "prompt_templates")
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self.model = self._resolve_model(model)
        self.system_prompt = system_prompt or self._load_default_system_prompt()
        self.max_iterations = max_iterations
        self.verbose = verbose
        self._event_handlers: List[AgentEventHandler] = list(event_handlers or [])

    # ── abstract interface ──────────────────────────────────────────

    @abstractmethod
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Return tool descriptions for the LLM."""
        ...

    @abstractmethod
    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call and return the result."""
        ...

    # ── model helpers ───────────────────────────────────────────────

    @staticmethod
    def _resolve_model(
        model: Optional[Union[str, BaseLLM]],
    ) -> BaseLLM:
        """Convert model string or instance to BaseLLM."""
        if isinstance(model, BaseLLM):
            return model
        return get_model(model)

    # ── prompt helpers ──────────────────────────────────────────────

    def _load_default_system_prompt(self) -> str:
        template = self._jinja_env.get_template("system_prompt.j2")
        return template.render()

    def _build_prompt(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
        history: List[ExecutionStep],
    ) -> str:
        tools_text = self._format_tools(available_tools)
        history_text = self._format_history(history)
        template = self._jinja_env.get_template("iteration_prompt.j2")
        return template.render(
            user_query=user_query,
            tools_text=tools_text,
            history_text=history_text,
        )

    def _format_tools(self, tools: List[Dict[str, Any]]) -> str:
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

    def _format_history(self, history: List[ExecutionStep]) -> str:
        if not history:
            return ""
        parts = []
        for step in history:
            parts.append(f"Iteration {step.iteration}:")
            parts.append(f"  Reasoning: {step.reasoning}")
            parts.append(f"  Action: {step.action}")
            if step.tool_calls:
                parts.append("  Tools called:")
                for tc in step.tool_calls:
                    parts.append(f"    - {tc.tool_name}")
            if step.tool_results:
                parts.append("  Results:")
                for tr in step.tool_results:
                    if tr.success:
                        parts.append(f"    - {tr.tool_name}: {tr.content}")
                    else:
                        parts.append(f"    - {tr.tool_name}: ERROR - {tr.error}")
            parts.append("")
        return "\n".join(parts)

    # ── ReAct loop ──────────────────────────────────────────────────

    async def run_async(self, user_query: str) -> AgentResult:
        """Execute the ReAct loop asynchronously."""
        history: List[ExecutionStep] = []
        iteration = 0

        await _emit(self._event_handlers, "on_agent_start", query=user_query)

        if self.verbose:
            print("\n" + "=" * 70)
            print("Agent Starting")
            print("=" * 70)
            print(f"Max iterations: {self.max_iterations}")

        available_tools = await self.get_available_tools()
        logger.info(f"[Agent] Discovered {len(available_tools)} tools")

        while iteration < self.max_iterations:
            iteration += 1
            if self.verbose:
                print(f"\n{'=' * 70}")
                print(f"Iteration {iteration}/{self.max_iterations}")
                print("=" * 70)

            step, should_finish = await self._execute_iteration(
                user_query, available_tools, history, iteration
            )
            history.append(step)

            if should_finish:
                if self.verbose:
                    print(f"\nAgent finished after {iteration} iteration(s)")
                if step.action == "finish" and step.tool_results:
                    tr = step.tool_results[0]
                    if tr.success:
                        result = AgentResult(
                            final_answer=tr.content,
                            execution_history=history,
                            iterations_used=len(history),
                            max_iterations_reached=False,
                            success=True,
                        )
                    else:
                        result = AgentResult(
                            final_answer="",
                            execution_history=history,
                            iterations_used=len(history),
                            max_iterations_reached=False,
                            success=False,
                            error=tr.error or "Unknown error",
                        )
                    await _emit(self._event_handlers, "on_agent_end", result=result)
                    return result

        if self.verbose:
            print(f"\nMax iterations ({self.max_iterations}) reached")

        result = AgentResult(
            final_answer="",
            execution_history=history,
            iterations_used=len(history),
            max_iterations_reached=True,
            success=False,
            error=(f"Agent did not complete task within {self.max_iterations} iterations."),
        )
        await _emit(self._event_handlers, "on_agent_end", result=result)
        return result

    def run(self, user_query: str) -> AgentResult:
        """Execute the agent synchronously."""
        return asyncio.run(self.run_async(user_query))

    # ── iteration helpers ───────────────────────────────────────────

    async def _execute_iteration(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
        history: List[ExecutionStep],
        iteration: int,
    ) -> Tuple[ExecutionStep, bool]:
        """Execute one ReAct iteration."""
        await _emit(self._event_handlers, "on_iteration_start", iteration=iteration)

        prompt = self._build_prompt(user_query, available_tools, history)
        action = await self._get_llm_action(prompt, iteration)
        if action is None:
            step = self._create_error_step(iteration, "Failed to parse LLM response")
            await _emit(
                self._event_handlers,
                "on_iteration_end",
                iteration=iteration,
                action="error",
            )
            return step, True

        if self.verbose:
            print(f"\n   Reasoning: {action.reasoning}")
            print(f"   Action: {action.action}")

        if action.action == "finish":
            result = self._handle_finish_action(action, iteration)
        elif action.action == "call_tool":
            result = await self._handle_tool_calls(action, iteration)
        else:
            result = self._handle_unknown_action(action, iteration)

        await _emit(
            self._event_handlers,
            "on_iteration_end",
            iteration=iteration,
            action=action.action,
        )
        return result

    async def _get_llm_action(self, prompt: str, iteration: int) -> Optional[AgentAction]:
        logger.info(f"[Agent] Iteration {iteration}: Sending prompt to LLM")
        if self.verbose:
            print("\nReasoning...")

        await _emit(self._event_handlers, "on_llm_start", iteration=iteration)

        try:
            response = self.model.generate(
                prompt=prompt,
                system_prompt=self.system_prompt,
                schema=AgentAction,
            )
            if isinstance(response, dict):
                action = AgentAction(**response)
            else:
                action = AgentAction(**json.loads(response))
            logger.info(
                f"[Agent] Iteration {iteration}: "
                f"Action={action.action}, "
                f"Reasoning='{action.reasoning[:100]}...'"
            )
            await _emit(self._event_handlers, "on_llm_end", action=action)
            return action
        except Exception as e:
            logger.error(
                f"[Agent] Failed to parse LLM response: {e}",
                exc_info=True,
            )
            await _emit(self._event_handlers, "on_error", error=e)
            return None

    def _handle_finish_action(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        logger.info("[Agent] Agent finishing")
        if self.verbose:
            ans = action.final_answer[:200] if action.final_answer else ""
            print(f"\nFinal Answer: {ans}...")
        return (
            ExecutionStep(
                iteration=iteration,
                reasoning=action.reasoning,
                action="finish",
                tool_calls=[],
                tool_results=[
                    ToolResult(
                        tool_name="finish",
                        success=True,
                        content=action.final_answer or "",
                    )
                ],
            ),
            True,
        )

    async def _handle_tool_calls(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        if not action.tool_calls:
            logger.warning("Action is 'call_tool' but no tool_calls provided")
            return (
                ExecutionStep(
                    iteration=iteration,
                    reasoning=action.reasoning,
                    action="call_tool",
                    tool_calls=[],
                    tool_results=[
                        ToolResult(
                            tool_name="error",
                            success=False,
                            error="No tool calls specified",
                        )
                    ],
                ),
                False,
            )

        tool_names = [tc.tool_name for tc in action.tool_calls]
        logger.info(f"[Agent] Calling {len(action.tool_calls)} tool(s): {tool_names}")
        if self.verbose:
            print(f"\nCalling {len(action.tool_calls)} tool(s):")
            for tc in action.tool_calls:
                print(f"   - {tc.tool_name}")

        tool_results = await self._execute_tools(action.tool_calls)
        return (
            ExecutionStep(
                iteration=iteration,
                reasoning=action.reasoning,
                action="call_tool",
                tool_calls=action.tool_calls,
                tool_results=tool_results,
            ),
            False,
        )

    async def _execute_tools(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        results: List[ToolResult] = []
        for tc in tool_calls:
            arguments = tc.arguments if isinstance(tc.arguments, dict) else {}
            await _emit(
                self._event_handlers,
                "on_tool_start",
                tool_name=tc.tool_name,
                arguments=arguments,
            )

            result = await self.execute_tool(tc)
            results.append(result)

            await _emit(
                self._event_handlers,
                "on_tool_end",
                tool_name=tc.tool_name,
                result=result,
            )

            if self.verbose:
                if result.success:
                    print(f"      + {result.tool_name}: {len(result.content)} chars")
                else:
                    print(f"      x {result.tool_name}: {result.error}")
        return results

    def _handle_unknown_action(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        logger.warning(f"Unknown action: {action.action}")
        return (
            ExecutionStep(
                iteration=iteration,
                reasoning=action.reasoning,
                action=action.action,
                tool_calls=[],
                tool_results=[
                    ToolResult(
                        tool_name="error",
                        success=False,
                        error=f"Unknown action: {action.action}",
                    )
                ],
            ),
            True,
        )

    def _create_error_step(self, iteration: int, error_msg: str) -> ExecutionStep:
        return ExecutionStep(
            iteration=iteration,
            reasoning=f"Error: {error_msg}",
            action="finish",
            tool_calls=[],
            tool_results=[
                ToolResult(
                    tool_name="error",
                    success=False,
                    error=error_msg,
                )
            ],
        )
