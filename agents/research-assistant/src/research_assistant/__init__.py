"""Research Assistant: AI-powered multi-agent reasoning system for scientific workflows."""

from research_assistant.graph import (
    create_multi_agent_coscientist,
    invoke_multi_agent,
)
from research_assistant.tools import ALL_TOOLS, get_tool_descriptions
from research_assistant.utils import format_agent_workflow


def __getattr__(name: str):
    """Lazy import for app to avoid circular import issues with __main__."""
    if name == "app":
        from research_assistant.app import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # FastAPI app (lazy loaded)
    "app",
    # Multi-agent
    "create_multi_agent_coscientist",
    "invoke_multi_agent",
    "format_agent_workflow",
    # Tools
    "ALL_TOOLS",
    "get_tool_descriptions",
]
