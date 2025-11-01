"""
Penelope: Intelligent Multi-Turn Testing Agent for AI Applications

Penelope executes complex, multi-turn test scenarios against AI targets.
She combines base testing intelligence with specific test instructions to
thoroughly evaluate AI systems across any dimension: security, user experience,
compliance, edge cases, and more.
"""

from rhesis.penelope.agent import PenelopeAgent
from rhesis.penelope.context import TestContext, TestResult, TestState
from rhesis.penelope.schemas import ToolCall
from rhesis.penelope.targets import EndpointTarget, Target
from rhesis.penelope.tools.base import Tool

__version__ = "0.1.0"

__all__ = [
    "PenelopeAgent",
    "TestContext",
    "TestResult",
    "TestState",
    "Tool",
    "ToolCall",
    "Target",
    "EndpointTarget",
]

