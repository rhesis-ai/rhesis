"""Agent factories for the Polymath multi-agent system.

Each agent lives in its own module so the prompt, tools, and construction
options stay self-contained — same shape as ``agents/research-assistant``.
"""

from polymath.agents.coordinator import create_agent as create_coordinator
from polymath.agents.info_specialist import create_agent as create_info_specialist
from polymath.agents.math_specialist import create_agent as create_math_specialist

ALL_AGENT_NAMES: list[str] = [
    "coordinator",
    "math_specialist",
    "info_specialist",
]

__all__ = [
    "ALL_AGENT_NAMES",
    "create_coordinator",
    "create_info_specialist",
    "create_math_specialist",
]
