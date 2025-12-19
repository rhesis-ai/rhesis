from .extractor import DocumentExtractor

# Re-export MCP components from mcp/ folder for backward compatibility
from .mcp import (
    MCPAgent,
    MCPClient,
    MCPClientFactory,
    ToolExecutor,
)

__all__ = [
    "DocumentExtractor",
    "MCPAgent",
    "MCPClient",
    "MCPClientFactory",
    "ToolExecutor",
]
