"""
Utility functions for the multi-agent Research Assistant system.

This module contains formatting, tracking, and helper utilities
used across the multi-agent workflow.
"""

from research_assistant.state import MultiAgentState
from research_assistant.tools import ANALYSIS_TOOLS, RETRIEVAL_TOOLS, SYNTHESIS_TOOLS
from research_assistant.transfers import TRANSFER_TOOLS

# =============================================================================
# TOOL TRACKING
# =============================================================================


def get_tool_layer(tool_name: str) -> str:
    """Get the layer a tool belongs to."""
    retrieval_names = [t.name for t in RETRIEVAL_TOOLS]
    analysis_names = [t.name for t in ANALYSIS_TOOLS]
    synthesis_names = [t.name for t in SYNTHESIS_TOOLS]
    transfer_names = [t.name for t in TRANSFER_TOOLS]

    if tool_name in retrieval_names:
        return "retrieval"
    elif tool_name in analysis_names:
        return "analysis"
    elif tool_name in synthesis_names:
        return "synthesis"
    elif tool_name in transfer_names:
        return "transfer"
    else:
        return "utility"


def track_tools_called(state: MultiAgentState, tools_executed: list[dict]) -> list[dict]:
    """Track which tools were called with metadata."""
    tools_called = list(state.get("tools_called", []))

    for tool_info in tools_executed:
        tools_called.append(
            {
                "tool_name": tool_info.get("name"),
                "tool_args": tool_info.get("args", {}),
                "tool_layer": get_tool_layer(tool_info.get("name", "")),
                "agent": state.get("active_agent", "unknown"),
            }
        )

    return tools_called


# =============================================================================
# FORMATTING UTILITIES
# =============================================================================

# Agent display labels with emojis
AGENT_LABELS = {
    "orchestrator": "🎯 Orchestrator",
    "safety_specialist": "🛡️ Safety",
    "target_specialist": "🎯 Target",
    "compound_specialist": "⚗️ Compound",
    "literature_specialist": "📚 Literature",
    "market_specialist": "📊 Market",
    "synthesis_agent": "📝 Synthesis",
}


def format_agent_workflow(agent_history: list[str]) -> str:
    """Format the agent workflow for display."""
    if not agent_history:
        return "No agents involved"

    labeled = [AGENT_LABELS.get(a, a) for a in agent_history]
    return " → ".join(labeled)


def format_tool_chain(tools_called: list[dict]) -> str:
    """Format the tool chain showing agents and tools."""
    if not tools_called:
        return "No tools called"

    # Group by agent
    by_agent: dict[str, list[str]] = {}
    for tool_info in tools_called:
        agent_name = tool_info.get("agent", "unknown")
        tool_name = tool_info.get("tool_name", "unknown")
        if agent_name not in by_agent:
            by_agent[agent_name] = []
        by_agent[agent_name].append(tool_name)

    parts = []
    for agent_name, tool_list in by_agent.items():
        tools_str = ", ".join(tool_list)
        parts.append(f"[{agent_name}] {tools_str}")

    return " → ".join(parts)
