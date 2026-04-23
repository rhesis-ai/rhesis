"""MCP (Model Context Protocol) client and agent for autonomous tool usage."""

from rhesis.sdk.agents.mcp.agent import MCPAgent
from rhesis.sdk.agents.mcp.client import MCPClient, MCPClientFactory
from rhesis.sdk.agents.mcp.exceptions import (
    MCPApplicationError,
    MCPConfigurationError,
    MCPConnectionError,
    MCPError,
    MCPValidationError,
)
from rhesis.sdk.agents.mcp.executor import ToolExecutor
from rhesis.sdk.agents.mcp.observable_agent import ObservableMCPAgent
from rhesis.sdk.agents.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolCall,
    ToolResult,
)

__all__ = [
    # Agent
    "MCPAgent",
    "ObservableMCPAgent",
    # Client
    "MCPClient",
    "MCPClientFactory",
    "ToolExecutor",
    # Exceptions
    "MCPError",
    "MCPConfigurationError",
    "MCPValidationError",
    "MCPApplicationError",
    "MCPConnectionError",
    # Schemas
    "AgentAction",
    "AgentResult",
    "ExecutionStep",
    "ToolCall",
    "ToolResult",
]
