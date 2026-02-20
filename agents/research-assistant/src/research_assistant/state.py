"""
State definitions for the multi-agent Research Assistant system.

This module defines the shared state that flows through the LangGraph workflow,
including the agent types and the state schema.
"""

from typing import Annotated, Any, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# =============================================================================
# AGENT TYPES
# =============================================================================

AgentType = Literal[
    "orchestrator",
    "safety_specialist",
    "target_specialist",
    "compound_specialist",
    "literature_specialist",
    "market_specialist",
    "synthesis_agent",
]

# All agent types as a list (useful for iteration)
ALL_AGENTS: list[AgentType] = [
    "orchestrator",
    "safety_specialist",
    "target_specialist",
    "compound_specialist",
    "literature_specialist",
    "market_specialist",
    "synthesis_agent",
]


# =============================================================================
# STATE DEFINITION
# =============================================================================


class MultiAgentState(TypedDict):
    """State for the multi-agent Research Assistant system."""

    messages: Annotated[list[BaseMessage], add_messages]
    conversation_id: str | None
    active_agent: AgentType
    agent_history: list[str]  # Track which agents have been involved
    tools_called: list[dict[str, Any]]
    handoff_count: int  # Guard against infinite loops
