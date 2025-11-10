"""Autonomous MCP Agent using ReAct (Reasoning + Action) loop."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.executor import ToolExecutor
from rhesis.sdk.services.mcp.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolResult,
)

logger = logging.getLogger(__name__)


class MCPAgent:
    """
    Autonomous AI agent that uses LLM to intelligently select and execute MCP tools.

    The agent operates in a ReAct loop (Reasoning + Action):
    1. Reason: Analyzes the task and available tools
    2. Act: Decides to call tools or finish with an answer
    3. Observe: Examines tool results
    4. Repeat until task is complete or max iterations reached

    This agent is server-agnostic and works with any MCP server (Notion,
    Slack, GitHub, etc.).
    """

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
- When you have sufficient information, use action="finish" with your final_answer
- Be efficient: minimize unnecessary tool calls
- You can call multiple tools in a single iteration if they don't depend on each other

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
        """
        Initialize the MCP Agent.

        Args:
            llm: An instance of BaseLLM (e.g., OpenAILLM, AnthropicLLM, etc.)
            mcp_client: MCP client instance (required)
            system_prompt: Optional custom system prompt. Uses DEFAULT_SYSTEM_PROMPT if not provided
            max_iterations: Maximum number of ReAct iterations (default: 10)
            verbose: If True, prints detailed execution information to stdout
            stop_on_error: If True, raises exception immediately on any error (default: True)

        Raises:
            ValueError: If mcp_client is not provided
        """
        if not mcp_client:
            raise ValueError("mcp_client is required")

        self.llm = llm
        self.mcp_client = mcp_client
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.stop_on_error = stop_on_error

        # Create tool executor
        self.executor = ToolExecutor(mcp_client)

    async def run_async(self, user_query: str) -> AgentResult:
        """
        Execute the autonomous agent to answer a query (async version).

        The agent will:
        1. Connect to MCP server and discover available tools
        2. Iteratively reason about the task and execute tools
        3. Continue until it has enough information to answer
        4. Return the final answer with full execution history

        Args:
            user_query: Natural language query/task for the agent to accomplish

        Returns:
            AgentResult with final answer, execution history, and metadata
        """
        execution_history: List[ExecutionStep] = []
        iteration = 0

        try:
            # Connect to MCP server
            await self.mcp_client.connect()
            logger.info("Connected to MCP server")

            if self.verbose:
                print("\n" + "=" * 70)
                print("🤖 MCP Agent Starting")
                print("=" * 70)
                print(f"Query: {user_query}")
                print(f"Max iterations: {self.max_iterations}")

            # Get available tools
            available_tools = await self.executor.get_available_tools()
            logger.info(f"Discovered {len(available_tools)} available tools")

            # ReAct loop
            while iteration < self.max_iterations:
                iteration += 1

                if self.verbose:
                    print(f"\n{'=' * 70}")
                    print(f"Iteration {iteration}/{self.max_iterations}")
                    print("=" * 70)

                # Execute one iteration
                step, should_finish = await self._execute_iteration(
                    user_query, available_tools, execution_history, iteration
                )

                execution_history.append(step)

                # Check if we should finish
                if should_finish:
                    if self.verbose:
                        print(f"\n✓ Agent finished after {iteration} iteration(s)")

                    if step.action == "finish":
                        final_answer = step.tool_results[0].content
                    else:
                        final_answer = ""

                    # Extract final answer from the last step if available
                    if not final_answer and execution_history:
                        # Look for finish action in history
                        for hist_step in reversed(execution_history):
                            if hist_step.action == "finish":
                                final_answer = hist_step.reasoning
                                break

                    return AgentResult(
                        final_answer=final_answer,
                        execution_history=execution_history,
                        iterations_used=iteration,
                        max_iterations_reached=False,
                        success=True,
                    )

            # Max iterations reached
            if self.verbose:
                print(f"\n⚠️  Max iterations ({self.max_iterations}) reached")

            return AgentResult(
                final_answer="Max iterations reached without completing the task. "
                "Please try again with a higher max_iterations value or a simpler query.",
                execution_history=execution_history,
                iterations_used=iteration,
                max_iterations_reached=True,
                success=False,
                error="Max iterations reached",
            )

        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            if self.verbose:
                print(f"\n❌ Error: {error_msg}")

            return AgentResult(
                final_answer="",
                execution_history=execution_history,
                iterations_used=iteration,
                max_iterations_reached=False,
                success=False,
                error=error_msg,
            )

        finally:
            await self.mcp_client.disconnect()
            logger.info("Disconnected from MCP server")

    def run(self, user_query: str) -> AgentResult:
        """
        Execute the autonomous agent to answer a query (synchronous wrapper).

        Args:
            user_query: Natural language query/task for the agent to accomplish

        Returns:
            AgentResult with final answer, execution history, and metadata
        """
        return asyncio.run(self.run_async(user_query))

    async def _execute_iteration(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
        execution_history: List[ExecutionStep],
        iteration: int,
    ) -> tuple[ExecutionStep, bool]:
        """
        Execute a single ReAct iteration.

        Args:
            user_query: The original user query
            available_tools: List of available tools from MCP server
            execution_history: History of previous steps
            iteration: Current iteration number

        Returns:
            Tuple of (ExecutionStep, should_finish)
        """
        # Build the prompt with history and available tools
        prompt = self._build_react_prompt(user_query, available_tools, execution_history)

        # Log the prompt being sent to LLM
        logger.info(f"[MCP_AGENT] Iteration {iteration}: Sending prompt to LLM")
        logger.info(f"[MCP_AGENT] System prompt: {self.system_prompt}")
        logger.info(f"[MCP_AGENT] User prompt: {prompt}")

        if self.verbose:
            print("\n💭 Reasoning...")

        # Get structured response from LLM
        try:
            response = self.llm.generate(
                prompt=prompt, system_prompt=self.system_prompt, schema=AgentAction
            )

            # Log the raw LLM response
            logger.info(f"[MCP_AGENT] LLM raw response: {response}")

            # Parse the response
            if isinstance(response, dict):
                action = AgentAction(**response)
            else:
                # If response is a string, try to parse it
                import json

                action = AgentAction(**json.loads(response))

            # Log the parsed action
            logger.info(
                f"[MCP_AGENT] Iteration {iteration}: Action={action.action}, "
                f"Reasoning='{action.reasoning[:100]}...'"
            )

        except Exception as e:
            logger.error(
                f"[MCP_AGENT] Failed to get structured response from LLM: {e}", exc_info=True
            )
            # Return an error step
            return (
                ExecutionStep(
                    iteration=iteration,
                    reasoning=f"Error: Failed to parse LLM response: {str(e)}",
                    action="finish",
                    tool_calls=[],
                    tool_results=[
                        ToolResult(
                            tool_name="llm_error",
                            success=False,
                            error=str(e),
                        )
                    ],
                ),
                True,
            )

        if self.verbose:
            print(f"\n   Reasoning: {action.reasoning}")
            print(f"   Action: {action.action}")

        # Handle finish action
        if action.action == "finish":
            logger.info("[MCP_AGENT] Agent finishing with final answer")
            logger.info(f"[MCP_AGENT] Final answer: {action.final_answer}")

            if self.verbose:
                print(f"\n✓ Final Answer: {action.final_answer}")

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

            # Log tool calls
            tool_names = [tc.tool_name for tc in action.tool_calls]
            logger.info(f"[MCP_AGENT] Calling {len(action.tool_calls)} tool(s): {tool_names}")
            for tc in action.tool_calls:
                logger.info(f"[MCP_AGENT] Tool call: {tc.tool_name} with args: {tc.arguments}")

            if self.verbose:
                print(f"\n🔧 Calling {len(action.tool_calls)} tool(s):")
                for tc in action.tool_calls:
                    print(f"   • {tc.tool_name}")

            # Execute all tool calls
            tool_results: List[ToolResult] = []
            for tool_call in action.tool_calls:
                result = await self.executor.execute_tool(tool_call)
                tool_results.append(result)

                # Log tool result
                if result.success:
                    logger.info(
                        f"[MCP_AGENT] Tool {result.tool_name} succeeded, "
                        f"returned {len(result.content)} chars"
                    )
                    logger.info(f"[MCP_AGENT] Tool {result.tool_name} result: {result.content}")
                else:
                    logger.error(f"[MCP_AGENT] Tool {result.tool_name} failed: {result.error}")

                if self.verbose:
                    if result.success:
                        print(f"      ✓ {result.tool_name}: {len(result.content)} chars")
                    else:
                        print(f"      ✗ {result.tool_name}: {result.error}")

                # Check for errors - abort if any tool fails
                if not result.success:
                    logger.error(f"[MCP_AGENT] Tool execution failed: {result.error}")
                    if self.stop_on_error:
                        raise RuntimeError(f"Tool '{result.tool_name}' failed: {result.error}")
                    return (
                        ExecutionStep(
                            iteration=iteration,
                            reasoning=action.reasoning,
                            action="call_tool",
                            tool_calls=action.tool_calls,
                            tool_results=tool_results,
                        ),
                        True,  # Finish on error
                    )

            return (
                ExecutionStep(
                    iteration=iteration,
                    reasoning=action.reasoning,
                    action="call_tool",
                    tool_calls=action.tool_calls,
                    tool_results=tool_results,
                ),
                False,  # Continue
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

    def _build_react_prompt(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
        execution_history: List[ExecutionStep],
    ) -> str:
        """
        Build the ReAct prompt with history and available tools.

        Args:
            user_query: The original user query
            available_tools: List of available tools
            execution_history: History of previous steps

        Returns:
            Formatted prompt string
        """
        # Format available tools
        tools_description = []
        for tool in available_tools:
            tool_desc = f"- {tool['name']}: {tool.get('description', 'No description')}"
            # Add input schema info if available
            if "inputSchema" in tool and tool["inputSchema"]:
                schema = tool["inputSchema"]
                if "properties" in schema:
                    params = ", ".join(schema["properties"].keys())
                    tool_desc += f"\n  Parameters: {params}"
            tools_description.append(tool_desc)

        tools_text = "\n".join(tools_description)

        # Format execution history
        history_text = ""
        if execution_history:
            history_parts = []
            for step in execution_history:
                history_parts.append(f"Iteration {step.iteration}:")
                history_parts.append(f"  Reasoning: {step.reasoning}")
                history_parts.append(f"  Action: {step.action}")

                if step.tool_calls:
                    history_parts.append("  Tools called:")
                    for tc in step.tool_calls:
                        history_parts.append(f"    • {tc.tool_name}")

                if step.tool_results:
                    history_parts.append("  Results:")
                    for tr in step.tool_results:
                        if tr.success:
                            history_parts.append(f"    • {tr.tool_name}: {tr.content}")
                        else:
                            history_parts.append(f"    • {tr.tool_name}: ERROR - {tr.error}")

                history_parts.append("")  # Empty line between iterations

            history_text = "\n".join(history_parts)

        # Build the full prompt
        prompt = f"""User Query: {user_query}

Available MCP Tools:
{tools_text}

"""

        if history_text:
            prompt += f"""Execution History:
{history_text}

Based on the query, available tools, and execution history above, decide what
to do next.

"""
        else:
            prompt += """This is the first iteration. Analyze the query and \
decide what tools to call.

"""

        prompt += """Your response should follow this structure:
- reasoning: Your step-by-step thinking about what to do
- action: Either "call_tool" (to execute tools) or "finish" (when you have the answer)
- tool_calls: List of tools to call if action="call_tool" (can be multiple)
- final_answer: Your complete answer if action="finish"

Think carefully about what information you need and how to get it efficiently."""

        return prompt
