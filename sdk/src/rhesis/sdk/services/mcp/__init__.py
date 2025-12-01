"""MCP (Model Context Protocol) client and agent for autonomous tool usage."""

from rhesis.sdk.services.mcp.agent import MCPAgent
from rhesis.sdk.services.mcp.client import MCPClient, MCPClientManager
from rhesis.sdk.services.mcp.exceptions import (
    MCPAuthenticationError,
    MCPConnectionError,
    MCPDataFormatError,
    MCPError,
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

__all__ = [
    # Agent
    "MCPAgent",
    # Client
    "MCPClient",
    "MCPClientManager",
    "ToolExecutor",
    # Exceptions
    "MCPError",
    "MCPAuthenticationError",
    "MCPNotFoundError",
    "MCPDataFormatError",
    "MCPConnectionError",
    # Schemas
    "AgentAction",
    "AgentResult",
    "ExecutionStep",
    "ToolCall",
    "ToolResult",
]
