"""MCP-specific schemas.

Re-exports shared schemas from rhesis.sdk.agents.schemas for convenience.
"""

# Re-export shared schemas so existing imports keep working
from rhesis.sdk.agents.schemas import (
    AgentAction,
    AgentResult,
    ExecutionStep,
    ToolCall,
    ToolResult,
)

__all__ = [
    "AgentAction",
    "AgentResult",
    "ExecutionStep",
    "ToolCall",
    "ToolResult",
]
