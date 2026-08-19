"""Stream parsing and response formatting for the Travel Agent.

Only presentation and event bookkeeping live here. The prose-scraping helpers this module
used to carry are gone: findings now travel in the trip brief, so nothing has to be
recovered from what an agent happened to say.
"""

from __future__ import annotations

import json
from typing import Any

from agent_framework import Content, Message

from travel_agent.router import COORDINATOR_NAME

AGENT_LABELS: dict[str, str] = {
    "trip_coordinator": "Coordinator",
    "destination_finder": "Surprise",
    "place_resolver": "Place",
    "sightseeing_scout": "Sightseeing",
    "dining_scout": "Dining",
    "conditions_scout": "Weather",
    "transit_planner": "Transit",
    "lodging_advisor": "Lodging",
}

# Text an agent emits for its own bookkeeping, which must never be served to the user.
INTERNAL_STATUS_PREFIXES: tuple[str, ...] = (
    "Replied to the user.",
    "TRIP BRIEF",
    "THIS TURN",
    "MISSING:",
)


def is_internal_status(text: str) -> bool:
    """Whether a chunk of agent text is internal bookkeeping rather than a reply."""
    stripped = text.strip()
    return any(stripped.startswith(prefix) for prefix in INTERNAL_STATUS_PREFIXES)


def format_agent_workflow(agent_history: list[str]) -> str:
    """Format the per-handoff agent history as ``A -> B -> C``."""
    if not agent_history:
        return "No agents involved"
    return " -> ".join(AGENT_LABELS.get(agent, agent) for agent in agent_history)


def format_tool_chain(tools_called: list[dict[str, Any]]) -> str:
    """Group tool invocations by agent for a one-line summary."""
    if not tools_called:
        return "No tools called"

    by_agent: dict[str, list[str]] = {}
    order: list[str] = []
    for tool_info in tools_called:
        agent_name = tool_info.get("agent", "unknown")
        if agent_name not in by_agent:
            by_agent[agent_name] = []
            order.append(agent_name)
        by_agent[agent_name].append(tool_info.get("tool_name", "unknown"))

    return " -> ".join(f"[{agent}] {', '.join(by_agent[agent])}" for agent in order)


def coerce_args(arguments: Any) -> dict[str, Any]:
    """Coerce a MAF ``function_call`` ``arguments`` payload into a plain dict.

    MAF carries tool arguments either as a JSON string (the OpenAI-compat path streams it
    that way) or as an already-decoded dict. Anything else is wrapped so the FastAPI
    response stays JSON-serialisable.
    """
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except (ValueError, TypeError):
            return {"raw": arguments}
    return {"value": arguments}


def record_function_calls(
    update: Any,
    *,
    tools_called: list[dict[str, Any]],
    agents_seen: list[str],
) -> None:
    """Pull domain tool invocations out of one streamed agent update."""
    author = getattr(update, "author_name", None) or "unknown"
    if author not in agents_seen:
        agents_seen.append(author)

    if getattr(update, "role", None) != "assistant":
        return

    for content in getattr(update, "contents", None) or ():
        if getattr(content, "type", None) != "function_call":
            continue
        tool_name = getattr(content, "name", None) or "unknown"
        # Handoff tools are framework routing signals, reported separately as agent edges.
        if tool_name.startswith("handoff_to_"):
            continue
        tools_called.append(
            {
                "tool_name": tool_name,
                "tool_args": coerce_args(getattr(content, "arguments", None)),
                "agent": author,
            }
        )


def collect_segment(
    update: Any,
    segments: list[dict[str, Any]],
) -> None:
    """Group contiguous streamed text chunks by author.

    Each ``output`` event is a delta, so one agent turn arrives as many partial chunks.
    Grouping by author and concatenating preserves word boundaries between them.
    """
    if getattr(update, "role", None) != "assistant":
        return
    text = getattr(update, "text", "") or ""
    if not text:
        return
    author = getattr(update, "author_name", None)
    if not segments or segments[-1]["author"] != author:
        segments.append({"author": author, "parts": []})
    segments[-1]["parts"].append(text)


def coordinator_text(segments: list[dict[str, Any]]) -> str | None:
    """The last thing the coordinator said, if it was meant for the user."""
    for segment in reversed(segments):
        if segment["author"] not in (COORDINATOR_NAME, None):
            continue
        joined = "".join(segment["parts"]).strip()
        if joined and not is_internal_status(joined):
            return joined
    return None


def user_message(text: str) -> Message:
    return Message(role="user", contents=[Content.from_text(text=text)])


def assistant_message(text: str) -> Message:
    """The single assistant message persisted for a completed turn."""
    return Message(
        role="assistant",
        contents=[Content.from_text(text=text)],
        author_name=COORDINATOR_NAME,
    )


def normalize_agent_order(agents_seen: list[str], handoff_targets: list[str]) -> list[str]:
    """Build the ordered, deduped list of agents that participated."""
    ordered: list[str] = []
    if COORDINATOR_NAME in agents_seen or COORDINATOR_NAME in handoff_targets:
        ordered.append(COORDINATOR_NAME)
    for name in [*agents_seen, *handoff_targets]:
        if name and name not in ordered:
            ordered.append(name)
    return ordered


__all__ = [
    "AGENT_LABELS",
    "COORDINATOR_NAME",
    "INTERNAL_STATUS_PREFIXES",
    "assistant_message",
    "coerce_args",
    "collect_segment",
    "coordinator_text",
    "format_agent_workflow",
    "format_tool_chain",
    "is_internal_status",
    "normalize_agent_order",
    "record_function_calls",
    "user_message",
]
