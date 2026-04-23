"""
Target abstractions for Penelope.

Targets represent what Penelope tests. Currently supports:
- EndpointTarget: Rhesis endpoints (via SDK)
- LangChainTarget: LangChain chains, agents, and runnables
- LangGraphTarget: LangGraph compiled graphs and agents

Future targets may include:
- AgentTarget: Other AI agents
- SystemTarget: Complete systems
- Custom targets: User-defined
"""

from rhesis.penelope.targets.endpoint import EndpointTarget
from rhesis.penelope.targets.langchain import LangChainTarget
from rhesis.penelope.targets.langgraph import LangGraphTarget
from rhesis.sdk.targets import Target, TargetResponse

__all__ = [
    "Target",
    "TargetResponse",
    "EndpointTarget",
    "LangChainTarget",
    "LangGraphTarget",
]
