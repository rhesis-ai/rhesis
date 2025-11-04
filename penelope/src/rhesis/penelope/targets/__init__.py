"""
Target abstractions for Penelope.

Targets represent what Penelope tests. Currently supports:
- EndpointTarget: Rhesis endpoints (via SDK)

Future targets may include:
- AgentTarget: Other AI agents
- SystemTarget: Complete systems
- Custom targets: User-defined
"""

from rhesis.penelope.targets.base import Target, TargetResponse
from rhesis.penelope.targets.endpoint import EndpointTarget

__all__ = [
    "Target",
    "TargetResponse",
    "EndpointTarget",
]
