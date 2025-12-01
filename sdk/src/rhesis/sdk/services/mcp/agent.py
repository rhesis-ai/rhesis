"""Generic MCP Agent using ReAct (Reason-Act-Observe) loop."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.exceptions import (
    MCPAuthenticationError,
    MCPConnectionError,
    MCPDataFormatError,
    MCPNotFoundError,
)
from rhesis.sdk.services.mcp.executor import ToolExecutor
from rhesis.sdk.services.mcp.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


class MCPAgent:
    """
    Generic MCP Agent for autonomous tool usage with customizable prompts.

    Uses a ReAct (Reason-Act-Observe) loop to autonomously call MCP tools
    and accomplish tasks. Clients can customize behavior via system prompts.
    """

    DEFAULT_SYSTEM_PROMPT = """You are an autonomous agent that can use MCP tools \
to accomplish tasks.

You operate in a ReAct loop: Reason → Act → Observe → Repeat

For each iteration:
- Reason: Think step-by-step about what information you need and how to get it
- Act: Either call tools to gather information, or finish with your final answer
- Observe: Examine tool results and plan next steps

Guidelines:
- Break complex tasks into simple tool calls
- Use tool results to inform next actions
- When you have sufficient information, use action="finish" with your final_answer
- Be efficient: minimize unnecessary tool calls
- You can call multiple tools in a single iteration if they don't depend on each other

Remember: You must explicitly use action="finish" when done."""

    def __init__(
        self,
        model: Optional[Union[str, BaseLLM]] = None,
        mcp_client: MCPClient = None,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10,
        verbose: bool = False,
    ):
        """
        Initialize the MCP agent.

        Args:
            model: Language model for reasoning and decision-making.
                Can be a string (provider name), BaseLLM instance, or None (uses default).
            mcp_client: Client connected to an MCP server
            system_prompt: Custom system prompt to define agent behavior (optional)
            max_iterations: Maximum reasoning loops before stopping (default: 10)
            verbose: Print detailed execution logs to stdout (default: False)
        """
        if not mcp_client:
            raise ValueError("mcp_client is required")

        # Convert model to BaseLLM instance if needed
        self.model = self._set_model(model)
        self.mcp_client = mcp_client
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.executor = ToolExecutor(mcp_client)

    def _set_model(self, model: Optional[Union[str, BaseLLM]]) -> BaseLLM:
        """Convert model string or instance to BaseLLM instance."""
        if isinstance(model, BaseLLM):
            return model
        return get_model(model)

    async def run_async(self, user_query: str) -> AgentResult:
        """
        Execute the agent's ReAct loop asynchronously.

        Connects to MCP server, discovers tools, and iteratively reasons about
        what actions to take until the task is complete or max iterations reached.

        Args:
            user_query: User's query or task description

        Returns:
            AgentResult with final answer and execution history
        """
        history: List[ExecutionStep] = []
        iteration = 0

        try:
            await self.mcp_client.connect()
            logger.info("[MCPAgent] Connected to MCP server")

            if self.verbose:
                print("\n" + "=" * 70)
                print("🤖 MCP Agent Starting")
                print("=" * 70)
                print(f"Max iterations: {self.max_iterations}")

            available_tools = await self.executor.get_available_tools()
            logger.info(f"[MCPAgent] Discovered {len(available_tools)} tools")

            # ReAct loop
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
                        print(f"\n✓ MCP Agent finished after {iteration} iteration(s)")

                    if step.action == "finish" and step.tool_results:
                        final_answer = step.tool_results[0].content
                        # Check for semantic errors in final_answer
                        self._check_semantic_errors(final_answer)
                        return AgentResult(
                            final_answer=final_answer,
                            execution_history=history,
                            iterations_used=len(history),
                            max_iterations_reached=False,
                            success=True,
                        )

            # Max iterations reached
            if self.verbose:
                print(f"\n⚠️  Max iterations ({self.max_iterations}) reached")

            raise MCPDataFormatError("Max iterations reached")

        except (
            MCPAuthenticationError,
            MCPNotFoundError,
            MCPDataFormatError,
        ):
            # Propagate MCP exceptions directly
            raise
        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            if self.verbose:
                print(f"\n❌ Error: {error_msg}")

            # Wrap unexpected errors
            raise MCPDataFormatError(f"Agent execution failed: {str(e)}", original_error=e)

        finally:
            await self.mcp_client.disconnect()
            logger.info("[MCPAgent] Disconnected from MCP server")

    def run(self, user_query: str) -> AgentResult:
        """
        Execute the agent synchronously.

        Convenience wrapper around run_async for non-async code.

        Args:
            user_query: User's query or task description

        Returns:
            AgentResult with final answer and execution history
        """
        return asyncio.run(self.run_async(user_query))

    async def _execute_iteration(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
        history: List[ExecutionStep],
        iteration: int,
    ) -> Tuple[ExecutionStep, bool]:
        """
        Execute one ReAct iteration: build prompt, get LLM decision, execute tools.

        Returns:
            Tuple of (execution_step, should_finish)
        """
        prompt = self._build_prompt(user_query, available_tools, history)

        # Get LLM decision
        action = await self._get_llm_action(prompt, iteration)
        if action is None:
            # LLM parsing error occurred
            return self._create_error_step(iteration, "Failed to parse LLM response"), True

        if self.verbose:
            print(f"\n   Reasoning: {action.reasoning}")
            print(f"   Action: {action.action}")

        # Handle different action types
        if action.action == "finish":
            return self._handle_finish_action(action, iteration)
        elif action.action == "call_tool":
            return await self._handle_tool_calls(action, iteration)
        else:
            return self._handle_unknown_action(action, iteration)

    async def _get_llm_action(self, prompt: str, iteration: int) -> Optional[AgentAction]:
        """Get and parse the LLM's action decision."""
        logger.info(f"[MCPAgent] Iteration {iteration}: Sending prompt to LLM")

        if self.verbose:
            print("\n💭 Reasoning...")

        try:
            response = self.model.generate(
                prompt=prompt, system_prompt=self.system_prompt, schema=AgentAction
            )

            if isinstance(response, dict):
                action = AgentAction(**response)
            else:
                action = AgentAction(**json.loads(response))

            logger.info(
                f"[MCPAgent] Iteration {iteration}: Action={action.action}, "
                f"Reasoning='{action.reasoning[:100]}...'"
            )
            return action

        except Exception as e:
            logger.error(f"[MCPAgent] Failed to parse LLM response: {e}", exc_info=True)
            return None

    def _handle_finish_action(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        """Handle the finish action."""
        logger.info("[MCPAgent] Agent finishing")

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

    async def _handle_tool_calls(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        """Handle tool call actions."""
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
        logger.info(f"[MCPAgent] Calling {len(action.tool_calls)} tool(s): {tool_names}")

        if self.verbose:
            print(f"\n🔧 Calling {len(action.tool_calls)} tool(s):")
            for tc in action.tool_calls:
                print(f"   • {tc.tool_name}")

        # Execute all tool calls
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
        """Execute multiple tool calls and return results."""
        tool_results: List[ToolResult] = []
        auth_failures = []

        for tool_call in tool_calls:
            try:
                result = await self.executor.execute_tool(tool_call)
                tool_results.append(result)

                # Logging
                if result.success:
                    logger.info(
                        f"[MCPAgent] Tool {result.tool_name} succeeded, "
                        f"returned {len(result.content)} chars"
                    )
                else:
                    logger.error(f"[MCPAgent] Tool {result.tool_name} failed: {result.error}")
                    # Check if this is an auth-related failure
                    if self._is_auth_error_in_result(result):
                        auth_failures.append(result.tool_name)

                if self.verbose:
                    if result.success:
                        print(f"      ✓ {result.tool_name}: {len(result.content)} chars")
                    else:
                        print(f"      ✗ {result.tool_name}: {result.error}")

            except (MCPAuthenticationError, MCPConnectionError):
                # Propagate clear tool-level errors immediately
                raise

        # If multiple tools failed with auth errors, raise authentication error
        if len(auth_failures) > 0:
            raise MCPAuthenticationError(
                f"Authentication failed for tools: {', '.join(auth_failures)}"
            )

        return tool_results

    def _handle_unknown_action(
        self, action: AgentAction, iteration: int
    ) -> Tuple[ExecutionStep, bool]:
        """Handle unknown action types."""
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
        """Create an error execution step."""
        return ExecutionStep(
            iteration=iteration,
            reasoning=f"Error: {error_msg}",
            action="finish",
            tool_calls=[],
            tool_results=[ToolResult(tool_name="error", success=False, error=error_msg)],
        )

    def _build_prompt(
        self, user_query: str, available_tools: List[Dict[str, Any]], history: List[ExecutionStep]
    ) -> str:
        """Build the user prompt for the current iteration."""
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
            prompt += """This is the first iteration. Analyze the query and decide \
what tools to call.

"""

        prompt += """Your response should follow this structure:
- reasoning: Your step-by-step thinking about what to do
- action: Either "call_tool" (to execute tools) or "finish" (when you have the answer)
- tool_calls: List of tools to call if action="call_tool" (can be multiple)
- final_answer: Your complete answer if action="finish"

Think carefully about what information you need and how to get it efficiently."""

        return prompt

    def _format_tools(self, tools: List[Dict[str, Any]]) -> str:
        """Format tool list into human-readable text with names, descriptions, \
and parameters."""
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

    def _check_semantic_errors(self, final_answer: str) -> None:
        """
        Check final_answer for semantic errors and raise appropriate exceptions.

        Args:
            final_answer: The agent's final answer

        Raises:
            MCPNotFoundError: If final_answer indicates item not found
        """
        if not final_answer:
            return

        final_answer_lower = final_answer.lower()

        # Check for "not found" indicators
        not_found_keywords = [
            "not found",
            "could not find",
            "does not exist",
            "no results found",
            "unable to find",
            "couldn't find",
        ]
        if any(keyword in final_answer_lower for keyword in not_found_keywords):
            raise MCPNotFoundError(f"Item not found: {final_answer}")

    def _is_auth_error_in_result(self, result: ToolResult) -> bool:
        """
        Check if tool result indicates an authentication error.

        Args:
            result: ToolResult to check

        Returns:
            True if result indicates authentication error
        """
        if not result.error:
            return False

        error_lower = result.error.lower()
        auth_keywords = [
            "unauthorized",
            "invalid api key",
            "authentication",
            "401",
            "403",
        ]
        return any(keyword in error_lower for keyword in auth_keywords)

    def _format_history(self, history: List[ExecutionStep]) -> str:
        """Format execution history into readable text for LLM context."""
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
                        parts.append(f"    • {tr.tool_name}: {tr.content}")
                    else:
                        parts.append(f"    • {tr.tool_name}: ERROR - {tr.error}")
            parts.append("")

        return "\n".join(parts)
