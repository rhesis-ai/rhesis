"""Observable MCP Agent with automatic observability using @observe decorator."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from rhesis.sdk.decorators import observe
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.mcp.agent import MCPAgent
from rhesis.sdk.services.mcp.client import MCPClient
from rhesis.sdk.services.mcp.exceptions import (
    MCPApplicationError,
    MCPConfigurationError,
    MCPConnectionError,
)
from rhesis.sdk.services.mcp.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


class ObservableMCPAgent(MCPAgent):
    """
    MCP Agent with automatic observability using @observe decorator.

    Inherits from MCPAgent and adds observability to key methods using the
    @observe decorator pattern:
    - LLM invocations (semantic: ai.llm.invoke)
    - Tool executions (semantic: ai.tool.invoke)
    - Agent iterations (function-level tracing)

    Note: Requires a RhesisClient to be initialized before use.

    Usage:
        from rhesis.sdk import RhesisClient
        from rhesis.sdk.services.mcp import ObservableMCPAgent

        # Initialize client first (or use backend's global client)
        client = RhesisClient(api_key="...", project_id="...")

        agent = ObservableMCPAgent(
            model=model,
            mcp_client=mcp_client,
            system_prompt=prompt,
        )
        result = await agent.run_async(query)  # Fully observable
    """

    def __init__(
        self,
        model: Optional[Union[str, BaseLLM]] = None,
        mcp_client: MCPClient = None,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10,
        verbose: bool = False,
    ):
        """Initialize the observable MCP agent."""
        super().__init__(
            model=model,
            mcp_client=mcp_client,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            verbose=verbose,
        )

        # Extract model name once during initialization for observability
        self.model_name = getattr(self.model, "model_name", None) or str(type(self.model).__name__)

    @observe(span_name="function.mcp_agent_run")
    async def run_async(self, user_query: str) -> AgentResult:
        """
        Execute the agent's ReAct loop with observability.

        Wraps the base implementation with observability tracking.
        All child operations (iterations, LLM calls, tool calls) are automatically traced.
        """
        # The @observe decorator handles span creation, status, and exception recording
        result = await super().run_async(user_query)
        return result

    @observe(span_name="function.mcp_agent_iteration")
    async def _execute_iteration(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
        history: List[ExecutionStep],
        iteration: int,
    ) -> Tuple[ExecutionStep, bool]:
        """
        Execute one ReAct iteration with observability.

        Tracks each iteration of the agent's reasoning loop.
        """
        # The @observe decorator handles the tracing
        step, should_finish = await super()._execute_iteration(
            user_query, available_tools, history, iteration
        )
        return step, should_finish

    @observe(span_name="ai.llm.invoke")
    async def _get_llm_action(self, prompt: str, iteration: int) -> Optional[AgentAction]:
        """
        Get LLM action decision with observability.

        Uses semantic layer for LLM operations (ai.llm.invoke).
        Model attributes and reasoning are added dynamically.
        """
        from opentelemetry import trace

        # Get the span created by @observe decorator
        span = trace.get_current_span()

        # Add LLM-specific attributes
        span.set_attribute("ai.operation.type", "llm.invoke")
        span.set_attribute("ai.model.name", self.model_name)
        span.set_attribute("ai.agent.iteration", iteration)

        try:
            logger.info(f"[ObservableMCPAgent] Iteration {iteration}: Sending prompt to LLM")

            if self.verbose:
                print("\n💭 Reasoning...")

            response = self.model.generate(
                prompt=prompt, system_prompt=self.system_prompt, schema=AgentAction
            )

            if isinstance(response, dict):
                action = AgentAction(**response)
            else:
                action = AgentAction(**json.loads(response))

            # Add reasoning as a span attribute for easy filtering
            span.set_attribute("ai.agent.reasoning", action.reasoning)
            span.set_attribute("ai.agent.action", action.action)

            logger.info(
                f"[ObservableMCPAgent] Iteration {iteration}: "
                f"Action={action.action}, "
                f"Reasoning='{action.reasoning[:100]}...'"
            )
            return action

        except Exception as e:
            # Exception is automatically recorded by @observe decorator
            logger.error(
                f"[ObservableMCPAgent] Failed to parse LLM response: {e}",
                exc_info=True,
            )
            return None

    async def _execute_tools(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """
        Execute multiple tool calls with observability.

        Uses semantic layer for tool operations (ai.tool.invoke).
        Each tool call is tracked individually with proper attributes.
        """
        tool_results: List[ToolResult] = []

        for tool_call in tool_calls:
            # Execute each tool with observability
            result = await self._execute_single_tool(tool_call)
            tool_results.append(result)

            # Logging (preserved from base implementation)
            if result.success:
                logger.info(
                    f"[ObservableMCPAgent] Tool {result.tool_name} succeeded, "
                    f"returned {len(result.content)} chars"
                )
            else:
                logger.warning(
                    f"[ObservableMCPAgent] Tool {result.tool_name} failed: {result.error}"
                )

            if self.verbose:
                if result.success:
                    print(f"      ✓ {result.tool_name}: {len(result.content)} chars")
                else:
                    print(f"      ✗ {result.tool_name}: {result.error}")

        return tool_results

    @observe(span_name="ai.tool.invoke")
    async def _execute_single_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a single tool call with observability.

        Uses semantic layer for tool operations with dynamic tool name.
        """
        from opentelemetry import trace

        # Get the span created by @observe decorator
        span = trace.get_current_span()

        # Add tool-specific attributes
        span.set_attribute("ai.operation.type", "tool.invoke")
        span.set_attribute("ai.tool.name", tool_call.tool_name)

        # Add tool arguments for debugging
        if tool_call.arguments:
            span.set_attribute("ai.tool.arguments", json.dumps(tool_call.arguments))

        try:
            result = await self.executor.execute_tool(tool_call)

            # Add tool attributes
            if result.success:
                span.set_attribute("ai.tool.output", result.content)
            else:
                span.set_attribute("ai.tool.error", result.error or "Unknown error")

            span.set_attribute("ai.tool.success", result.success)

            return result

        except (MCPConnectionError, MCPConfigurationError, MCPApplicationError):
            # Infrastructure/config/application failures - propagate immediately
            # Exception is automatically recorded by @observe decorator
            raise
        except Exception as e:
            # Wrap unexpected errors as ToolResult
            # Exception is automatically recorded by @observe decorator
            logger.error(
                f"[ObservableMCPAgent] Unexpected error executing tool {tool_call.tool_name}: {e}",
                exc_info=True,
            )
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                error=str(e),
            )
