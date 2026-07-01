"""Multi-agent workflow construction and invocation for Travel Agent."""

from __future__ import annotations

import asyncio
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
from travel_agent.utils import (
    COORDINATOR_NAME,
    capture_final_text,
    format_agent_workflow,
    format_tool_chain,
    normalize_agent_order,
    record_function_calls,
    resolve_response,
    segment_texts,
    user_visible_assistant_message,
)

WORKFLOW_TIMEOUT_SECONDS = 120

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
    # Always pass a ``list[Message]`` to ``Workflow.run``. Its ``message`` param
    # is typed ``Any`` and is forwarded to the start executor, which accepts a
    # message list (the multi-turn path already relied on this by passing
    # ``[*conversation_history, user_msg]``). Using the list form uniformly keeps
    # single-turn and multi-turn runs on the same, verified input shape.
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
                record_function_calls(data, tools_called=tools_called, agents_seen=agents_seen)
                if getattr(data, "role", None) == "assistant":
                    text = getattr(data, "text", "") or ""
                    if text:
                        author = getattr(data, "author_name", None)
                        if not assistant_segments or assistant_segments[-1]["author"] != author:
                            assistant_segments.append({"author": author, "parts": []})
                        assistant_segments[-1]["parts"].append(text)
                continue

            if event_type == "request_info":
                captured = capture_final_text(data, fallback=segment_texts(assistant_segments))
                if captured:
                    final_text = captured
                continue

    # ``asyncio.wait_for`` raises ``asyncio.TimeoutError`` which is only an alias
    # of the builtin ``TimeoutError`` on Python 3.11+. Normalize to the builtin so
    # callers (e.g. the FastAPI ``/chat`` route) can catch ``TimeoutError`` on
    # every supported Python version.
    try:
        await asyncio.wait_for(_consume_events(), timeout=WORKFLOW_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"Travel workflow timed out after {WORKFLOW_TIMEOUT_SECONDS}s") from exc

    response_text, final_agent = resolve_response(
        assistant_segments,
        final_text=final_text,
    )
    if not response_text:
        raise RuntimeError("Travel workflow completed without producing a user-facing response.")

    agents_involved = normalize_agent_order(agents_seen, handoff_targets)
    updated_history = [*(conversation_history or []), user_msg]
    updated_history.append(user_visible_assistant_message(response_text))

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
