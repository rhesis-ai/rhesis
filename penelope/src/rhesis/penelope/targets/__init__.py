"""
Target abstractions for Penelope.

Targets represent what Penelope tests. Currently supports:
- EndpointTarget: Rhesis endpoints (via SDK)
- LangChainTarget: LangChain chains, agents, and runnables
- LangGraphTarget: LangGraph compiled graphs and agents
- MAFTarget: MAF (Microsoft Agent Framework) agents
- PydanticAITarget: Pydantic AI agents

Future targets may include:
- AgentTarget: Other AI agents
- SystemTarget: Complete systems
- Custom targets: User-defined
"""

from rhesis.penelope.targets.endpoint import EndpointTarget
from rhesis.penelope.targets.haystack import HaystackTarget
from rhesis.penelope.targets.langchain import LangChainTarget
from rhesis.penelope.targets.langgraph import LangGraphTarget
from rhesis.penelope.targets.maf import MAFTarget
from rhesis.penelope.targets.pydantic_ai import PydanticAITarget
from rhesis.sdk.targets import Target, TargetResponse

__all__ = [
    "Target",
    "TargetResponse",
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
