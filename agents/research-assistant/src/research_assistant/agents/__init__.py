"""
Agents module for the Research Assistant multi-agent system.

Each agent is defined in its own module with its prompt, tools, and node factory.
"""

from research_assistant.agents.base import create_agent_node, create_llm_with_tools
from research_assistant.agents.compound import create_node as create_compound_node
from research_assistant.agents.literature import create_node as create_literature_node
from research_assistant.agents.market import create_node as create_market_node
from research_assistant.agents.orchestrator import create_node as create_orchestrator_node
from research_assistant.agents.safety import create_node as create_safety_node
from research_assistant.agents.synthesis import create_node as create_synthesis_node
from research_assistant.agents.target import create_node as create_target_node

__all__ = [
    # Base utilities
    "create_agent_node",
    "create_llm_with_tools",
    # Agent node factories
    "create_orchestrator_node",
    "create_safety_node",
    "create_target_node",
    "create_compound_node",
    "create_literature_node",
    "create_market_node",
    "create_synthesis_node",
]
