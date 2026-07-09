"""
Penelope: Intelligent Multi-Turn Testing Agent for AI Applications

Penelope executes complex, multi-turn test scenarios against AI targets.
She combines base testing intelligence with specific test instructions to
thoroughly evaluate AI systems across any dimension: security, user experience,
compliance, edge cases, and more.
"""

from rhesis.penelope.agent import PenelopeAgent
from rhesis.penelope.config import PenelopeConfig
from rhesis.penelope.context import TestContext, TestResult, TestState
from rhesis.penelope.schemas import (
    AnalyzeResponseParams,
    AssistantMessage,
    ExtractInformationParams,
    FunctionCall,
    MessageToolCall,
    SendMessageParams,
    ToolCall,
    ToolMessage,
)
from rhesis.penelope.targets import (
    EndpointTarget,
    HaystackTarget,
    LangChainTarget,
    LangGraphTarget,
    MAFTarget,
    PydanticAITarget,
    Target,
)
from rhesis.penelope.tools.base import Tool

__version__ = "0.1.0"

__all__ = [
    "PenelopeAgent",
    "PenelopeConfig",
    "TestContext",
    "TestResult",
    "TestState",
    "AssistantMessage",
    "FunctionCall",
    "MessageToolCall",
    "ToolMessage",
    "Tool",
    "ToolCall",
    "SendMessageParams",
    "AnalyzeResponseParams",
    "ExtractInformationParams",
    "Target",
    "EndpointTarget",
    "HaystackTarget",
    "LangChainTarget",
    "LangGraphTarget",
    "MAFTarget",
    "PydanticAITarget",
]

# Deprecated alias: MicrosoftAgentFrameworkTarget was renamed to MAFTarget.
_DEPRECATED_ALIASES = {"MicrosoftAgentFrameworkTarget": MAFTarget}


def __getattr__(name: str):
    if name in _DEPRECATED_ALIASES:
        import warnings

        warnings.warn(
            f"{name} is deprecated; use MAFTarget instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _DEPRECATED_ALIASES[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
