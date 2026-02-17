"""Rhesis SDK agents package.

Provides base classes for building agents and tools, the MCPAgent
for MCP-based tool usage, and the ArchitectAgent for conversational
test suite design.
"""

from typing import List, Optional

from rhesis.sdk.agents.architect import (
    ArchitectAgent,
    ArchitectPlan,
    MetricSpec,
    ProjectSpec,
    TestSetSpec,
)
from rhesis.sdk.agents.base import BaseAgent, BaseTool, MCPTool
from rhesis.sdk.agents.events import AgentEventHandler
from rhesis.sdk.agents.mcp import (
    MCPAgent,
    MCPClient,
    MCPClientFactory,
    ObservableMCPAgent,
    ToolExecutor,
)
from rhesis.sdk.agents.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolCall,
    ToolResult,
)
from rhesis.sdk.agents.tools import ExploreEndpointTool


def get_rhesis_tools(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> List[MCPTool]:
    """Get Rhesis platform tools via the backend's MCP endpoint.

    Connects to the backend's MCP server over HTTP. Uses SDK config
    (RHESIS_API_KEY, RHESIS_BASE_URL) as defaults.

    Args:
        base_url: Backend base URL. Defaults to SDK config.
        api_key: API key. Defaults to SDK config.

    Returns:
        List containing an MCPTool connected to the backend's MCP
        endpoint. The MCPTool expands into individual tools at
        runtime via list_tools().
    """
    from rhesis.sdk.config import get_api_key, get_base_url

    resolved_url = base_url or get_base_url()
    resolved_key = api_key or get_api_key()
    mcp_url = f"{resolved_url.rstrip('/')}/mcp"

    return [MCPTool.from_url(mcp_url, api_key=resolved_key)]


__all__ = [
    # Base classes
    "BaseAgent",
    "BaseTool",
    "MCPTool",
    # Tools
    "ExploreEndpointTool",
    # Events
    "AgentEventHandler",
    # MCP agent
    "MCPAgent",
    "ObservableMCPAgent",
    "MCPClient",
    "MCPClientFactory",
    "ToolExecutor",
    # Architect agent
    "ArchitectAgent",
    "ArchitectPlan",
    "ProjectSpec",
    "TestSetSpec",
    "MetricSpec",
    # Schemas
    "AgentAction",
    "AgentResult",
    "ExecutionStep",
    "ToolCall",
    "ToolResult",
    # Factory
    "get_rhesis_tools",
]
