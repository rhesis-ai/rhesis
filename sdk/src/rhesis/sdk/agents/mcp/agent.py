"""MCP Agent using ReAct (Reason-Act-Observe) loop.

Extends BaseAgent with MCP-specific tool discovery and execution.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rhesis.sdk.agents.base import BaseAgent
from rhesis.sdk.agents.events import AgentEventHandler
from rhesis.sdk.agents.mcp.client import MCPClient
from rhesis.sdk.agents.mcp.exceptions import (
    MCPApplicationError,
    MCPConfigurationError,
    MCPConnectionError,
    MCPValidationError,
)
from rhesis.sdk.agents.mcp.executor import ToolExecutor
from rhesis.sdk.agents.schemas import (
    AgentResult,
    ToolCall,
    ToolResult,
)
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


class MCPAgent(BaseAgent):
    """MCP Agent for autonomous tool usage with customizable prompts.

    Uses a ReAct (Reason-Act-Observe) loop to autonomously call MCP
    tools and accomplish tasks. Extends BaseAgent with MCP-specific
    client and executor integration.
    """

    def __init__(
        self,
        model: Optional[Union[str, BaseLLM]] = None,
        mcp_client: Optional[MCPClient] = None,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10,
        verbose: bool = False,
        event_handlers: Optional[List[AgentEventHandler]] = None,
    ):
        if not mcp_client:
            raise ValueError("mcp_client is required")

        self.mcp_client = mcp_client
        self.executor = ToolExecutor(mcp_client)

        super().__init__(
            model=model,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            verbose=verbose,
            prompt_templates_dir=(Path(__file__).parent / "prompt_templates"),
            event_handlers=event_handlers,
        )

    # ── BaseAgent interface ─────────────────────────────────────────

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get tools from the MCP server."""
        return await self.executor.get_available_tools()

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool via the MCP executor."""
        try:
            return await self.executor.execute_tool(tool_call)
        except (
            MCPConnectionError,
            MCPConfigurationError,
            MCPApplicationError,
        ):
            raise

    # ── MCP-specific run_async override ─────────────────────────────

    async def run_async(self, user_query: str) -> AgentResult:
        """Execute the agent's ReAct loop with MCP lifecycle.

        Handles MCP server connection/disconnection and wraps
        errors in MCP-specific exception types.
        """
        try:
            try:
                await self.mcp_client.connect()
            except ConnectionError as e:
                raise MCPConnectionError(
                    f"Failed to connect to MCP server: {str(e)}",
                    original_error=e,
                )
            logger.info("[MCPAgent] Connected to MCP server")

            result = await super().run_async(user_query)

            if result.max_iterations_reached:
                raise MCPValidationError(
                    f"Agent did not complete task within "
                    f"{self.max_iterations} iterations. "
                    "Consider increasing max_iterations or "
                    "simplifying the task."
                )

            return result

        except (
            MCPConnectionError,
            MCPConfigurationError,
            MCPValidationError,
            MCPApplicationError,
        ):
            raise
        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.verbose:
                print(f"\nError: {error_msg}")
            raise MCPValidationError(
                f"Agent execution failed: {str(e)}",
                original_error=e,
            )
        finally:
            await self.mcp_client.disconnect()
            logger.info("[MCPAgent] Disconnected from MCP server")
