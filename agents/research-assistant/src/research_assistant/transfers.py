"""
Transfer tools for agent handoffs in the multi-agent system.

Transfer tools enable agents to hand off control to other specialists
when their domain expertise is needed.
"""

from langchain_core.tools import tool

from research_assistant.state import AgentType

# =============================================================================
# TRANSFER TOOLS - Enable handoffs between agents
# =============================================================================


@tool(return_direct=True)
def transfer_to_orchestrator() -> str:
    """
    Transfer control back to the orchestrator agent.
    Use this when you've completed your analysis and want to hand off
    for synthesis or to route to another specialist.
    """
    return "Transferred to orchestrator"


@tool(return_direct=True)
def transfer_to_safety_specialist() -> str:
    """
    Transfer to the Safety Specialist for safety and toxicity analysis.
    Use when the query involves:
    - Safety profiles and toxicity data
    - Adverse events and risk assessment
    - Regulatory safety concerns
    - On-target and off-target effects
    """
    return "Transferred to safety specialist"


@tool(return_direct=True)
def transfer_to_target_specialist() -> str:
    """
    Transfer to the Target Specialist for target biology analysis.
    Use when the query involves:
    - Target biology and function
    - Genetic validation and disease associations
    - Expression profiles and pathways
    - Target druggability assessment
    """
    return "Transferred to target specialist"


@tool(return_direct=True)
def transfer_to_compound_specialist() -> str:
    """
    Transfer to the Compound Specialist for chemical analysis.
    Use when the query involves:
    - Compound properties and structure
    - ADMET profiles
    - Synthesis routes and optimization
    - SAR (Structure-Activity Relationship) analysis
    """
    return "Transferred to compound specialist"


@tool(return_direct=True)
def transfer_to_literature_specialist() -> str:
    """
    Transfer to the Literature Specialist for scientific literature search.
    Use when the query involves:
    - Scientific publications and reviews
    - Patent searches and IP analysis
    - Clinical trial publications
    - State of the art research
    """
    return "Transferred to literature specialist"


@tool(return_direct=True)
def transfer_to_market_specialist() -> str:
    """
    Transfer to the Market Specialist for market intelligence.
    Use when the query involves:
    - Market size and growth analysis
    - Competitor landscape
    - Pipeline analysis
    - Business strategy and positioning
    """
    return "Transferred to market specialist"


@tool(return_direct=True)
def transfer_to_synthesis_agent() -> str:
    """
    Transfer to the Synthesis Agent for final report generation.
    Use when you have gathered enough data and need to:
    - Create comprehensive reports
    - Generate final recommendations
    - Synthesize insights from multiple sources
    - Produce executive summaries
    """
    return "Transferred to synthesis agent"


# =============================================================================
# TRANSFER TOOL COLLECTIONS AND MAPPINGS
# =============================================================================

# All transfer tools
TRANSFER_TOOLS = [
    transfer_to_orchestrator,
    transfer_to_safety_specialist,
    transfer_to_target_specialist,
    transfer_to_compound_specialist,
    transfer_to_literature_specialist,
    transfer_to_market_specialist,
    transfer_to_synthesis_agent,
]

# Mapping from transfer tool name to agent type
TRANSFER_TOOL_TO_AGENT: dict[str, AgentType] = {
    "transfer_to_orchestrator": "orchestrator",
    "transfer_to_safety_specialist": "safety_specialist",
    "transfer_to_target_specialist": "target_specialist",
    "transfer_to_compound_specialist": "compound_specialist",
    "transfer_to_literature_specialist": "literature_specialist",
    "transfer_to_market_specialist": "market_specialist",
    "transfer_to_synthesis_agent": "synthesis_agent",
}


def get_next_agent_from_tool_call(tool_name: str) -> AgentType | None:
    """Get the next agent based on a transfer tool call."""
    return TRANSFER_TOOL_TO_AGENT.get(tool_name)
