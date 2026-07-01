"""Multi-agent workflow construction and invocation for Travel Agent."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from agent_framework import Agent, Content, Message, Workflow
from agent_framework_orchestrations import HandoffBuilder, HandoffSentEvent

from travel_agent.agents import (
    create_coordinator,
    create_destination_finder,
    create_logistics_planner,
    create_sightseeing_scout,
)
from travel_agent.client import build_chat_client
from travel_agent.utils import format_agent_workflow, format_tool_chain

WORKFLOW_TIMEOUT_SECONDS = 120
COORDINATOR_NAME = "trip_coordinator"

# Autonomous-mode retry prompt for specialists that reply without handing back.
# Replaces MAF's generic "Continue assisting autonomously" default with a
# targeted nudge so the next turn returns control to the coordinator.
_HANDOFF_BACK_PROMPT = (
    "Call the handoff_to_trip_coordinator tool now to return control to the "
    "coordinator. Do not reply with more text."
)


def build_travel_workflow() -> Workflow:
    """Construct the compiled multi-agent handoff workflow."""
    client = build_chat_client()
    coordinator = create_coordinator(client)
    destination_finder = create_destination_finder(client)
    sightseeing_scout = create_sightseeing_scout(client)
    logistics_planner = create_logistics_planner(client)

    return (
        HandoffBuilder(
            name="travel_agent_handoff",
            participants=[
                coordinator,
                destination_finder,
                sightseeing_scout,
                logistics_planner,
            ],
            description=(
                "Travel Agent demo: coordinator routes to destination, sightseeing, "
                "and logistics specialists before synthesising the trip plan."
            ),
        )
        .with_start_agent(coordinator)
        .add_handoff(
            coordinator,
            [destination_finder, sightseeing_scout, logistics_planner],
        )
        .add_handoff(destination_finder, [coordinator])
        .add_handoff(sightseeing_scout, [coordinator])
        .add_handoff(logistics_planner, [coordinator])
        # Autonomous mode is scoped to the specialists only. The coordinator is
        # deliberately left non-autonomous so its first no-handoff response (the
        # synthesized plan) is terminal: MAF emits ``request_info`` and the run
        # stops, instead of re-prompting the coordinator to "Continue assisting
        # autonomously" up to the turn limit. The specialists get a couple of
        # autonomous turns as a retry safety net: if a specialist replies with
        # plain text instead of handing back, the targeted prompt below nudges
        # it to call its handoff tool so control returns to the coordinator
        # (otherwise ``request_info`` would fire from the specialist and the
        # coordinator would never get to synthesize the final plan).
        .with_autonomous_mode(
            agents=[destination_finder, sightseeing_scout, logistics_planner],
            prompts={
                "destination_finder": _HANDOFF_BACK_PROMPT,
                "sightseeing_scout": _HANDOFF_BACK_PROMPT,
                "logistics_planner": _HANDOFF_BACK_PROMPT,
            },
            turn_limits={
                "destination_finder": 2,
                "sightseeing_scout": 2,
                "logistics_planner": 2,
            },
        )
        .build()
    )


def _coerce_args(arguments: Any) -> dict[str, Any]:
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


def _record_function_calls(
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
                "tool_args": _coerce_args(getattr(content, "arguments", None)),
                "agent": author,
            }
        )


def _segment_texts(segments: list[dict[str, Any]]) -> list[str]:
    """Concatenate each segment's streamed chunks into one non-empty string each."""
    texts: list[str] = []
    for segment in segments:
        joined = "".join(segment["parts"]).strip()
        if joined:
            texts.append(joined)
    return texts


def _last_segment_text(segments: list[dict[str, Any]], *, author: str) -> str | None:
    """Return the concatenated text of the last contiguous segment by ``author``."""
    for segment in reversed(segments):
        if segment["author"] == author:
            joined = "".join(segment["parts"]).strip()
            if joined:
                return joined
    return None


def _user_visible_assistant_message(text: str) -> Message:
    """Build the single assistant message persisted for a completed turn."""
    return Message(
        role="assistant",
        contents=[Content.from_text(text=text)],
        author_name=COORDINATOR_NAME,
    )


def _capture_final_text(request_info_data: Any, *, fallback: list[str]) -> str | None:
    """Pull the synthesised final answer out of a handoff request-info event."""
    agent_response = getattr(request_info_data, "agent_response", None)
    text = getattr(agent_response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    if fallback:
        joined = "\n".join(text for text in fallback if text).strip()
        return joined or None
    return None


def _normalize_agent_order(agents_seen: list[str], handoff_targets: list[str]) -> list[str]:
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


def _resolve_response(
    assistant_segments: list[dict[str, Any]],
    *,
    final_text: str | None,
) -> tuple[str, str]:
    """Pick the user-facing response text and the agent that authored it."""
    coordinator_text = _last_segment_text(assistant_segments, author=COORDINATOR_NAME)
    if coordinator_text:
        return coordinator_text, COORDINATOR_NAME

    if final_text:
        return final_text, COORDINATOR_NAME

    for segment in reversed(assistant_segments):
        joined = "".join(segment["parts"]).strip()
        if joined:
            author = segment.get("author") or "unknown"
            return joined, author

    return "", "unknown"


async def invoke_travel_workflow_async(
    workflow: Workflow,
    user_message: str,
    *,
    conversation_history: list[Message] | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Run the workflow once and return a structured result."""
    handoff_targets: list[str] = []
    tools_called: list[dict[str, Any]] = []
    agents_seen: list[str] = []
    # In streaming mode each ``output`` event is an ``AgentResponseUpdate``
    # delta, so a single agent turn arrives as many partial-text chunks. We
    # group contiguous chunks by author into segments and concatenate the raw
    # text per segment, so word boundaries between chunks are preserved.
    assistant_segments: list[dict[str, Any]] = []
    final_text: str | None = None

    user_msg = Message(role="user", contents=[Content.from_text(text=user_message)])
    workflow_input = [*(conversation_history or []), user_msg]

    async def _consume_events() -> None:
        nonlocal final_text
        async for event in workflow.run(workflow_input, stream=True):
            event_type = getattr(event, "type", None)
            data = getattr(event, "data", None)

            if event_type == "handoff_sent" and isinstance(data, HandoffSentEvent):
                handoff_targets.append(data.target)
                continue

            if event_type == "output" and data is not None:
                _record_function_calls(data, tools_called=tools_called, agents_seen=agents_seen)
                if getattr(data, "role", None) == "assistant":
                    text = getattr(data, "text", "") or ""
                    if text:
                        author = getattr(data, "author_name", None)
                        if not assistant_segments or assistant_segments[-1]["author"] != author:
                            assistant_segments.append({"author": author, "parts": []})
                        assistant_segments[-1]["parts"].append(text)
                continue

            if event_type == "request_info":
                captured = _capture_final_text(data, fallback=_segment_texts(assistant_segments))
                if captured:
                    final_text = captured
                continue

    await asyncio.wait_for(_consume_events(), timeout=WORKFLOW_TIMEOUT_SECONDS)

    response_text, final_agent = _resolve_response(
        assistant_segments,
        final_text=final_text,
    )
    if not response_text:
        raise RuntimeError("Travel workflow completed without producing a user-facing response.")

    agents_involved = _normalize_agent_order(agents_seen, handoff_targets)
    updated_history = [*(conversation_history or []), user_msg]
    updated_history.append(_user_visible_assistant_message(response_text))

    return {
        "response": response_text,
        "messages": updated_history,
        "tools_called": tools_called,
        "agents_involved": agents_involved,
        "agent_workflow": format_agent_workflow(agents_involved),
        "tool_chain": format_tool_chain(tools_called),
        "conversation_id": conversation_id,
        "agent": final_agent,
    }


def invoke_travel_workflow(
    workflow: Workflow,
    user_message: str,
    *,
    conversation_history: list[Message] | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Sync wrapper around :func:`invoke_travel_workflow_async`."""
    return asyncio.run(
        invoke_travel_workflow_async(
            workflow,
            user_message,
            conversation_history=conversation_history,
            conversation_id=conversation_id,
        )
    )


async def run_query(query: str) -> dict[str, Any]:
    """Build a fresh workflow and run a single query.

    A new workflow is built per call on purpose: the participating agents use
    ``require_per_service_call_history_persistence=True``, so a shared instance
    would carry one caller's conversation context into later calls (cross-session
    leakage in a multi-user or long-lived service).
    """
    return await invoke_travel_workflow_async(build_travel_workflow(), query)


def get_participants(workflow: Workflow) -> list[Agent]:
    """Return the participating ``Agent`` instances on a built workflow."""
    try:
        executors = workflow.executors  # type: ignore[attr-defined]
        agents: list[Agent] = []
        for executor in executors.values() if hasattr(executors, "values") else []:
            agent = getattr(executor, "agent", None)
            if isinstance(agent, Agent):
                agents.append(agent)
        return agents
    except Exception:  # noqa: BLE001
        return []


__all__ = [
    "COORDINATOR_NAME",
    "WORKFLOW_TIMEOUT_SECONDS",
    "build_travel_workflow",
    "get_participants",
    "invoke_travel_workflow",
    "invoke_travel_workflow_async",
    "run_query",
]
