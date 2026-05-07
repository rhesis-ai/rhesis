"""Polymath: a Microsoft Agent Framework multi-agent demo for SDK trace testing."""

from polymath.utils import format_agent_workflow, format_tool_chain
from polymath.workflow import (
    build_workflow,
    invoke_polymath,
    invoke_polymath_async,
)


def __getattr__(name: str):
    """Lazy import for ``app`` to avoid circular imports with ``__main__``."""
    if name == "app":
        from polymath.app import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "app",
    "build_workflow",
    "format_agent_workflow",
    "format_tool_chain",
    "invoke_polymath",
    "invoke_polymath_async",
]
