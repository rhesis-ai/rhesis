"""MCP (Model Context Protocol) Agent and utilities for autonomous tool usage."""

from rhesis.sdk.services.mcp.agents import BaseMCPAgent, MCPAgent, MCPExtractAgent, MCPSearchAgent
from rhesis.sdk.services.mcp.client import MCPClient, MCPClientManager
from rhesis.sdk.services.mcp.executor import ToolExecutor
from rhesis.sdk.services.mcp.provider_config import (
    GITHUB_CONFIG,
    NOTION_CONFIG,
    SLACK_CONFIG,
    ProviderConfig,
)
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
    "BaseMCPAgent",
    "MCPAgent",
    "MCPSearchAgent",
    "MCPExtractAgent",
    # Clients
    "MCPClient",
    "MCPClientManager",
    "ToolExecutor",
    # Provider Configurations
    "ProviderConfig",
    "NOTION_CONFIG",
    "GITHUB_CONFIG",
    "SLACK_CONFIG",
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
