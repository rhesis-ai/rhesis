"""
Tools for Penelope agent.

Following Anthropic's principle of high-quality Agent-Computer Interfaces (ACI),
these tools are extensively documented with clear usage patterns, examples, and edge cases.
"""

from rhesis.penelope.tools.analysis import AnalysisTool
from rhesis.penelope.tools.base import Tool, ToolResult
from rhesis.penelope.tools.target_interaction import TargetInteractionTool

__all__ = [
    "Tool",
    "ToolResult",
    "TargetInteractionTool",
    "AnalysisTool",
]
