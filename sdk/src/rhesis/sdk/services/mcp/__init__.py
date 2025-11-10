"""MCP (Model Context Protocol) Agent and utilities for autonomous tool usage."""

from rhesis.sdk.services.mcp.agents import MCPAgent, MCPExtractAgent, MCPSearchAgent
from rhesis.sdk.services.mcp.client import MCPClient, MCPClientManager
from rhesis.sdk.services.mcp.executor import ToolExecutor
from rhesis.sdk.services.mcp.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ExtractedPage,
    ExtractionResult,
    PageMetadata,
    SearchResult,
    ToolCall,
    ToolResult,
)

__all__ = [
    # Agents
    "MCPAgent",
    "MCPSearchAgent",
    "MCPExtractAgent",
    # Clients
    "MCPClient",
    "MCPClientManager",
    "ToolExecutor",
    # Schemas - General
    "AgentAction",
    "AgentResult",
    "ExecutionStep",
    "ToolCall",
    "ToolResult",
    # Schemas - Search & Extract
    "PageMetadata",
    "SearchResult",
    "ExtractedPage",
    "ExtractionResult",
]
