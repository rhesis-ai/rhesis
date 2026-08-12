"""Formatting and stream-parsing helpers for the Travel Agent multi-agent system."""

from __future__ import annotations

import json
import logging
from typing import Any

from agent_framework import Content, Message

logger = logging.getLogger(__name__)

COORDINATOR_NAME = "trip_coordinator"

# Served when the coordinator never produced user-facing text. Specialist prose is
# never promoted in its place: specialists write internal notes addressed to the
# coordinator, and one that stalls (for example because no destination reached it)
# apologises to "the user" it thinks it is talking to.
FALLBACK_RESPONSE = (
    "I could not put a trip plan together this time. Tell me a destination - or ask for "
    "a surprise one - and I will try again."
)

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


def coerce_args(arguments: Any) -> dict[str, Any]:
    """Coerce a MAF ``function_call`` ``arguments`` payload into a plain dict.

    MAF carries tool arguments either as a JSON string (the OpenAI-compat
    path streams it that way) or as an already-decoded ``dict``. Anything
    else is wrapped so the FastAPI response stays JSON-serialisable.
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
    role = getattr(update, "role", None)
    author = getattr(update, "author_name", None) or "unknown"
    if author not in agents_seen:
        agents_seen.append(author)

    if role != "assistant":
        return

    for content in getattr(update, "contents", None) or ():
        if getattr(content, "type", None) != "function_call":
            continue
        tool_name = getattr(content, "name", None) or "unknown"
        if tool_name.startswith("handoff_to_"):
            continue
        tools_called.append(
            {
                "tool_name": tool_name,
                "tool_args": coerce_args(getattr(content, "arguments", None)),
                "agent": author,
            }
        )


def segment_texts(segments: list[dict[str, Any]], *, author: str | None = None) -> list[str]:
    """Concatenate each segment's streamed chunks into one non-empty string each.

    Pass ``author`` to keep only the segments that agent authored.
    """
    texts: list[str] = []
    for segment in segments:
        if author is not None and segment.get("author") != author:
            continue
        joined = "".join(segment["parts"]).strip()
        if joined:
            texts.append(joined)
    return texts


def last_segment_text(segments: list[dict[str, Any]], *, author: str) -> str | None:
    """Return the concatenated text of the last contiguous segment by ``author``."""
    for segment in reversed(segments):
        if segment["author"] == author:
            joined = "".join(segment["parts"]).strip()
            if joined:
                return joined
    return None


def user_visible_assistant_message(text: str) -> Message:
    """Build the single assistant message persisted for a completed turn."""
    return Message(
        role="assistant",
        contents=[Content.from_text(text=text)],
        author_name=COORDINATOR_NAME,
    )


def authored_by_specialist(agent_response: Any) -> bool:
    """Report whether a handoff response was written by a specialist, not the coordinator.

    ``request_info`` fires from whichever agent ended its turn without handing off, so
    the event can carry a specialist's internal note. Messages with no ``author_name``
    are treated as the coordinator's: the check only rejects a known other agent.
    """
    for message in getattr(agent_response, "messages", None) or ():
        author = getattr(message, "author_name", None)
        if author and author != COORDINATOR_NAME:
            return True
    return False


def capture_final_text(request_info_data: Any, *, fallback: list[str]) -> str | None:
    """Pull the coordinator's synthesised final answer out of a handoff request-info event."""
    agent_response = getattr(request_info_data, "agent_response", None)
    text = getattr(agent_response, "text", None)
    if isinstance(text, str) and text.strip() and not authored_by_specialist(agent_response):
        return text
    if fallback:
        joined = "\n".join(text for text in fallback if text).strip()
        return joined or None
    return None


def normalize_agent_order(agents_seen: list[str], handoff_targets: list[str]) -> list[str]:
    """Build the ordered, deduped list of agents that participated."""
    ordered: list[str] = []
    if "trip_coordinator" in agents_seen or "trip_coordinator" in handoff_targets:
        ordered.append("trip_coordinator")
    for agent_name in agents_seen:
        if agent_name and agent_name not in ordered:
            ordered.append(agent_name)
    for target in handoff_targets:
        if target and target not in ordered:
            ordered.append(target)
    return ordered


def resolve_response(
    assistant_segments: list[dict[str, Any]],
    *,
    final_text: str | None,
) -> tuple[str, str]:
    """Pick the user-facing response text and the agent that authored it.

    Only the coordinator's text is ever served. A specialist's segment is internal
    research addressed to the coordinator, so when the coordinator produced nothing we
    log the miss and serve :data:`FALLBACK_RESPONSE` rather than leaking that note.
    """
    coordinator_text = last_segment_text(assistant_segments, author=COORDINATOR_NAME)
    if coordinator_text:
        return coordinator_text, COORDINATOR_NAME

    if final_text:
        return final_text, COORDINATOR_NAME

    logger.warning(
        "Coordinator produced no user-facing text; serving the fallback response. "
        "Segments seen from: %s",
        [segment.get("author") for segment in assistant_segments],
    )
    return FALLBACK_RESPONSE, COORDINATOR_NAME
