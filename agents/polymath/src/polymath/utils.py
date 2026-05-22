"""Formatting helpers for the Polymath multi-agent system.

Same shape as :mod:`research_assistant.utils` so the API responses look
familiar across the two demo agents.
"""

from __future__ import annotations

# Display labels keyed by agent name.
AGENT_LABELS: dict[str, str] = {
    "coordinator": "Coordinator",
    "math_specialist": "Math",
    "info_specialist": "Info",
}


def format_agent_workflow(agent_history: list[str]) -> str:
    """Format the per-handoff agent history as ``A -> B -> C``."""
    if not agent_history:
        return "No agents involved"
    labeled = [AGENT_LABELS.get(a, a) for a in agent_history]
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
