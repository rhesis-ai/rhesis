"""Formatting helpers for the Travel Agent multi-agent system."""

from __future__ import annotations

AGENT_LABELS: dict[str, str] = {
    "trip_coordinator": "Coordinator",
    "destination_finder": "Destination",
    "sightseeing_scout": "Sightseeing",
    "logistics_planner": "Logistics",
}


def format_agent_workflow(agent_history: list[str]) -> str:
    """Format the per-handoff agent history as ``A -> B -> C``."""
    if not agent_history:
        return "No agents involved"
    labeled = [AGENT_LABELS.get(agent, agent) for agent in agent_history]
    return " -> ".join(labeled)


def format_tool_chain(tools_called: list[dict]) -> str:
    """Group tool invocations by agent for a one-line summary."""
    if not tools_called:
        return "No tools called"

    by_agent: dict[str, list[str]] = {}
    order: list[str] = []
    for tool_info in tools_called:
        agent_name = tool_info.get("agent", "unknown")
        tool_name = tool_info.get("tool_name", "unknown")
        if agent_name not in by_agent:
            by_agent[agent_name] = []
            order.append(agent_name)
        by_agent[agent_name].append(tool_name)

    parts = [f"[{agent_name}] {', '.join(by_agent[agent_name])}" for agent_name in order]
    return " -> ".join(parts)
