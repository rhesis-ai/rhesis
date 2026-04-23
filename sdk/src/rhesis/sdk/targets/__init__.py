"""Target abstractions for testing agents.

Defines the ``Target`` interface that represents any system a testing
agent can interact with, and ``TargetResponse`` for structured results.

Concrete implementations live in their respective packages:
- ``rhesis.penelope.targets.EndpointTarget`` -- SDK REST client
- ``rhesis.penelope.targets.LangChainTarget`` -- LangChain runnables
- ``rhesis.penelope.targets.LangGraphTarget`` -- LangGraph graphs
- ``rhesis.sdk.agents.targets.LocalEndpointTarget`` -- callable-based (backend worker)
"""

from rhesis.sdk.targets.base import Target, TargetResponse

__all__ = [
    "Target",
    "TargetResponse",
]
