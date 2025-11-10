"""Base MCP Agent with shared ReAct loop logic."""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.executor import ToolExecutor
from rhesis.sdk.services.mcp.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolResult,
)

if TYPE_CHECKING:
    from rhesis.sdk.services.mcp.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class BaseMCPAgent(ABC):
    """Base class for MCP agents using ReAct loop. Subclasses override specific methods."""

    def __init__(
        self,
        llm: BaseLLM,
        mcp_client: MCPClient,
        max_iterations: int = 10,
        verbose: bool = False,
        stop_on_error: bool = True,
        provider_config: Optional["ProviderConfig"] = None,
    ):
        if not mcp_client:
            raise ValueError("mcp_client is required")
        self.llm = llm
        self.mcp_client = mcp_client
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.stop_on_error = stop_on_error
        self.executor = ToolExecutor(mcp_client, provider_config=provider_config)

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent type."""
        pass

    @abstractmethod
    def build_prompt(
        self,
        task_input: Any,
        available_tools: List[Dict[str, Any]],
        history: List[ExecutionStep],
    ) -> str:
        """Build the task-specific prompt."""
        pass

    @abstractmethod
    def parse_result(self, final_answer: str, history: List[ExecutionStep]) -> Any:
        """Parse the final answer into the appropriate result type."""
        pass

    @abstractmethod
    def create_error_result(self, error: str, history: List[ExecutionStep], iterations: int) -> Any:
        """Create an error result object."""
        pass

    def get_agent_name(self) -> str:
        """Return agent display name for logging."""
        return self.__class__.__name__

    async def run_async(self, task_input: Any) -> Any:
        """Execute the agent with given input (async version)."""
        history: List[ExecutionStep] = []
        iteration = 0

        try:
            await self.mcp_client.connect()
            logger.info(f"[{self.get_agent_name()}] Connected to MCP server")

            if self.verbose:
                print("\n" + "=" * 70)
                print(f"{self.get_agent_name()} Starting")
                print("=" * 70)
                print(f"Max iterations: {self.max_iterations}")

            available_tools = await self.executor.get_available_tools()
            logger.info(f"[{self.get_agent_name()}] Discovered {len(available_tools)} tools")

            # ReAct loop
            while iteration < self.max_iterations:
                iteration += 1

                if self.verbose:
                    print(f"\n{'=' * 70}")
                    print(f"Iteration {iteration}/{self.max_iterations}")
                    print("=" * 70)

                step, should_finish = await self._execute_iteration(
                    task_input, available_tools, history, iteration
                )
                history.append(step)

                if should_finish:
                    if self.verbose:
                        print(
                            f"\n✓ {self.get_agent_name()} finished after {iteration} iteration(s)"
                        )

                    if step.action == "finish" and step.tool_results:
                        final_answer = step.tool_results[0].content
                        return self.parse_result(final_answer, history)

            # Max iterations reached
            if self.verbose:
                print(f"\n⚠️  Max iterations ({self.max_iterations}) reached")

            return self.create_error_result("Max iterations reached", history, iteration)

        except Exception as e:
            error_msg = f"{self.get_agent_name()} execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            if self.verbose:
                print(f"\n❌ Error: {error_msg}")

            return self.create_error_result(str(e), history, iteration)

        finally:
            await self.mcp_client.disconnect()
            logger.info(f"[{self.get_agent_name()}] Disconnected from MCP server")

    def run(self, task_input: Any) -> Any:
        """Execute the agent (synchronous wrapper)."""
        return asyncio.run(self.run_async(task_input))

    async def _execute_iteration(
        self,
        task_input: Any,
        available_tools: List[Dict[str, Any]],
        history: List[ExecutionStep],
        iteration: int,
    ) -> Tuple[ExecutionStep, bool]:
        """Execute a single ReAct iteration."""
        prompt = self.build_prompt(task_input, available_tools, history)

        logger.info(f"[{self.get_agent_name()}] Iteration {iteration}: Sending prompt to LLM")

        if self.verbose:
            print("\n💭 Reasoning...")

        # Get structured response from LLM
        try:
            response = self.llm.generate(
                prompt=prompt, system_prompt=self.get_system_prompt(), schema=AgentAction
            )

            if isinstance(response, dict):
                action = AgentAction(**response)
            else:
                action = AgentAction(**json.loads(response))

            logger.info(
                f"[{self.get_agent_name()}] Iteration {iteration}: Action={action.action}, "
                f"Reasoning='{action.reasoning[:100]}...'"
            )

        except Exception as e:
            logger.error(
                f"[{self.get_agent_name()}] Failed to parse LLM response: {e}",
                exc_info=True,
            )
            return (
                ExecutionStep(
                    iteration=iteration,
                    reasoning=f"Error: Failed to parse LLM response: {str(e)}",
                    action="finish",
                    tool_calls=[],
                    tool_results=[ToolResult(tool_name="llm_error", success=False, error=str(e))],
                ),
                True,
            )

        if self.verbose:
            print(f"\n   Reasoning: {action.reasoning}")
            print(f"   Action: {action.action}")

        # Handle finish action
        if action.action == "finish":
            logger.info(f"[{self.get_agent_name()}] Agent finishing")

            if self.verbose:
                ans = action.final_answer[:200] if action.final_answer else ""
                print(f"\n✓ Final Answer: {ans}...")

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

        # Handle tool calls
        if action.action == "call_tool":
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
            logger.info(
                f"[{self.get_agent_name()}] Calling {len(action.tool_calls)} tool(s): {tool_names}"
            )

            if self.verbose:
                print(f"\n🔧 Calling {len(action.tool_calls)} tool(s):")
                for tc in action.tool_calls:
                    print(f"   • {tc.tool_name}")

            # Execute all tool calls
            tool_results: List[ToolResult] = []
            for tool_call in action.tool_calls:
                result = await self.executor.execute_tool(tool_call)

                # Format the content for LLM consumption
                if result.success and result.content:
                    result.content = self._format_tool_content(result.content)

                tool_results.append(result)

                if result.success:
                    logger.info(
                        f"[{self.get_agent_name()}] Tool {result.tool_name} succeeded, "
                        f"returned {len(result.content)} chars"
                    )
                else:
                    logger.error(
                        f"[{self.get_agent_name()}] Tool {result.tool_name} failed: {result.error}"
                    )

                if self.verbose:
                    if result.success:
                        print(f"      ✓ {result.tool_name}: {len(result.content)} chars")
                    else:
                        print(f"      ✗ {result.tool_name}: {result.error}")

                if not result.success and self.stop_on_error:
                    raise RuntimeError(f"Tool '{result.tool_name}' failed: {result.error}")

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

        # Unknown action
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

    def _format_tools(self, tools: List[Dict[str, Any]]) -> str:
        """Format available tools for prompt."""
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

    def _format_history(self, history: List[ExecutionStep], max_len: int = 5000) -> str:
        """Format execution history for prompt."""
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
                    parts.append(f"    • {tc.tool_name}")

            if step.tool_results:
                parts.append("  Results:")
                for tr in step.tool_results:
                    if tr.success:
                        if len(tr.content) > max_len:
                            trunc = f"\n... (truncated, total {len(tr.content)} chars)"
                            content = tr.content[:max_len] + trunc
                        else:
                            content = tr.content
                        parts.append(f"    • {tr.tool_name}: {content}")
                    else:
                        parts.append(f"    • {tr.tool_name}: ERROR - {tr.error}")
            parts.append("")

        return "\n".join(parts)

    def _format_tool_content(self, content: str) -> str:
        """
        Format tool content for LLM consumption.

        Attempts to parse JSON and format it in a readable way. Falls back to
        raw content if not JSON.

        Args:
            content: Raw content from tool execution

        Returns:
            Formatted content suitable for LLM
        """
        try:
            # Try to parse as JSON first for structured data
            data = json.loads(content)

            # For simple dicts, create key-value pairs
            if isinstance(data, dict):
                # Check if it's a simple dict that can be formatted nicely
                if len(data) <= 10 and not any(isinstance(v, (dict, list)) for v in data.values()):
                    parts = []
                    for key, value in data.items():
                        parts.append(f"{key}: {value}")
                    return "\n".join(parts)

            # For complex structures, return compact JSON (no indentation)
            # This prevents issues with LLM trying to include formatted JSON in its response
            return json.dumps(data, ensure_ascii=False)

        except json.JSONDecodeError:
            # If not JSON, use as plain text
            return content


class MCPAgent(BaseMCPAgent):
    """General-purpose MCP Agent for backward compatibility."""

    DEFAULT_SYSTEM_PROMPT = """You are an autonomous agent that can use MCP \
tools to accomplish tasks.

You operate in a ReAct loop: Reason → Act → Observe → Repeat

For each iteration:
- Reason: Think step-by-step about what information you need and how to get it
- Act: Either call tools to gather information, or finish with your final answer
- Observe: Examine tool results and plan next steps

Guidelines:
- Break complex tasks into simple tool calls
- Use tool results to inform next actions
- When you have sufficient information, use action="finish" with your \
final_answer
- Be efficient: minimize unnecessary tool calls
- You can call multiple tools in a single iteration if they don't depend on \
each other

Remember: You must explicitly use action="finish" when done."""

    def __init__(
        self,
        llm: BaseLLM,
        mcp_client: MCPClient,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10,
        verbose: bool = False,
        stop_on_error: bool = True,
    ):
        super().__init__(llm, mcp_client, max_iterations, verbose, stop_on_error)
        self.custom_system_prompt = system_prompt

    def get_system_prompt(self) -> str:
        return self.custom_system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def get_agent_name(self) -> str:
        return "🤖 MCP Agent"

    def build_prompt(
        self, task_input: Any, available_tools: List[Dict[str, Any]], history: List[ExecutionStep]
    ) -> str:
        user_query = str(task_input)
        tools_text = self._format_tools(available_tools)
        history_text = self._format_history(history)

        prompt = f"""User Query: {user_query}

Available MCP Tools:
{tools_text}

"""
        if history_text:
            prompt += f"""Execution History:
{history_text}

Based on the query, available tools, and execution history above, decide what to do next.

"""
        else:
            prompt += """This is the first iteration. Analyze the query and \
decide what tools to call.

"""

        prompt += """Your response should follow this structure:
- reasoning: Your step-by-step thinking about what to do
- action: Either "call_tool" (to execute tools) or "finish" (when you have \
the answer)
- tool_calls: List of tools to call if action="call_tool" (can be multiple)
- final_answer: Your complete answer if action="finish"

Think carefully about what information you need and how to get it \
efficiently."""

        return prompt

    def parse_result(self, final_answer: str, history: List[ExecutionStep]) -> AgentResult:
        return AgentResult(
            final_answer=final_answer,
            execution_history=history,
            iterations_used=len(history),
            max_iterations_reached=False,
            success=True,
        )

    def create_error_result(
        self, error: str, history: List[ExecutionStep], iterations: int
    ) -> AgentResult:
        return AgentResult(
            final_answer="",
            execution_history=history,
            iterations_used=iterations,
            max_iterations_reached="Max iterations" in error,
            success=False,
            error=error,
        )

    # Keep backward compatibility
    async def run_async(self, user_query: str) -> AgentResult:
        return await super().run_async(user_query)

    def run(self, user_query: str) -> AgentResult:
        return super().run(user_query)
