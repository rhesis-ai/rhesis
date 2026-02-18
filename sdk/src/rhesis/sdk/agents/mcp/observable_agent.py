"""Observable MCP Agent with automatic observability via @observe."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from rhesis.sdk.agents.mcp.agent import MCPAgent
from rhesis.sdk.agents.mcp.client import MCPClient
from rhesis.sdk.agents.mcp.exceptions import (
    MCPApplicationError,
    MCPConfigurationError,
    MCPConnectionError,
)
from rhesis.sdk.agents.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolCall,
    ToolResult,
)
from rhesis.sdk.decorators import observe
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


class ObservableMCPAgent(MCPAgent):
    """MCP Agent with automatic observability using @observe.

    Inherits from MCPAgent and adds observability to key methods:
    - LLM invocations (semantic: ai.llm.invoke)
    - Tool executions (semantic: ai.tool.invoke)
    - Agent iterations (function-level tracing)

    Usage:
        from rhesis.sdk import RhesisClient
        from rhesis.sdk.agents.mcp import ObservableMCPAgent

        client = RhesisClient(api_key="...", project_id="...")
        agent = ObservableMCPAgent(
            model=model,
            mcp_client=mcp_client,
            system_prompt=prompt,
        )
        result = await agent.run_async(query)
    """

    def __init__(
        self,
        model: Optional[Union[str, BaseLLM]] = None,
        mcp_client: Optional[MCPClient] = None,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10,
        verbose: bool = False,
    ):
        super().__init__(
            model=model,
            mcp_client=mcp_client,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            verbose=verbose,
        )
        self.model_name = getattr(self.model, "model_name", None) or str(type(self.model).__name__)

    @observe(span_name="function.mcp_agent_run")
    async def run_async(self, user_query: str) -> AgentResult:
        """Execute the ReAct loop with observability."""
        result = await super().run_async(user_query)
        return result

    @observe(span_name="function.mcp_agent_iteration")
    async def _execute_iteration(
        self,
        user_query: str,
        available_tools: List[Dict[str, Any]],
        iteration: int,
    ) -> Tuple[ExecutionStep, bool]:
        """Execute one ReAct iteration with observability."""
        step, should_finish = await super()._execute_iteration(
            user_query, available_tools, iteration
        )
        return step, should_finish

    @observe(span_name="ai.llm.invoke")
    async def _get_llm_action(self, prompt: str, iteration: int) -> Optional[AgentAction]:
        """Get LLM action decision with observability."""
        from opentelemetry import trace

        span = trace.get_current_span()
        span.set_attribute("ai.operation.type", "llm.invoke")
        span.set_attribute("ai.model.name", self.model_name)
        span.set_attribute("ai.agent.iteration", iteration)

        try:
            logger.info(f"[ObservableMCPAgent] Iteration {iteration}: Sending prompt to LLM")
            if self.verbose:
                print("\nReasoning...")

            response = self.model.generate(
                prompt=prompt,
                system_prompt=self.system_prompt,
                schema=AgentAction,
            )
            if isinstance(response, dict):
                action = AgentAction(**response)
            else:
                action = AgentAction(**json.loads(response))

            span.set_attribute("ai.agent.reasoning", action.reasoning)
            span.set_attribute("ai.agent.action", action.action)

            logger.info(
                f"[ObservableMCPAgent] Iteration {iteration}: "
                f"Action={action.action}, "
                f"Reasoning='{action.reasoning[:100]}...'"
            )
            return action

        except Exception as e:
            logger.error(
                f"[ObservableMCPAgent] Failed to parse LLM response: {e}",
                exc_info=True,
            )
            return None

    async def _execute_tools(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """Execute multiple tool calls with observability."""
        tool_results: List[ToolResult] = []

        for tool_call in tool_calls:
            result = await self._execute_single_tool(tool_call)
            tool_results.append(result)

            if result.success:
                logger.info(
                    f"[ObservableMCPAgent] Tool "
                    f"{result.tool_name} succeeded, "
                    f"returned {len(result.content)} chars"
                )
            else:
                logger.warning(
                    f"[ObservableMCPAgent] Tool {result.tool_name} failed: {result.error}"
                )

            if self.verbose:
                if result.success:
                    print(f"      + {result.tool_name}: {len(result.content)} chars")
                else:
                    print(f"      x {result.tool_name}: {result.error}")

        return tool_results

    @observe(span_name="ai.tool.invoke")
    async def _execute_single_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call with observability."""
        from opentelemetry import trace

        span = trace.get_current_span()
        span.set_attribute("ai.operation.type", "tool.invoke")
        span.set_attribute("ai.tool.name", tool_call.tool_name)

        if tool_call.arguments:
            span.set_attribute(
                "ai.tool.arguments",
                json.dumps(tool_call.arguments),
            )

        try:
            result = await self.executor.execute_tool(tool_call)

            if result.success:
                span.set_attribute("ai.tool.output", result.content)
            else:
                span.set_attribute(
                    "ai.tool.error",
                    result.error or "Unknown error",
                )
            span.set_attribute("ai.tool.success", result.success)
            return result

        except (
            MCPConnectionError,
            MCPConfigurationError,
            MCPApplicationError,
        ):
            raise
        except Exception as e:
            logger.error(
                f"[ObservableMCPAgent] Unexpected error executing tool {tool_call.tool_name}: {e}",
                exc_info=True,
            )
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                error=str(e),
            )
