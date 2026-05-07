"""Multi-agent workflow construction and invocation for Polymath.

Builds a Microsoft Agent Framework :class:`HandoffBuilder` workflow with three
participants -- coordinator, math specialist, info specialist -- and exposes
both async and sync entry points so the FastAPI app and the example CLI can
share a single implementation.

Autonomous mode is enabled so the workflow runs end-to-end without
human-in-the-loop input. That is the right shape for a *trace generator*: we
want the workflow to actually finish, hit every span, and return cleanly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agent_framework import Agent, Message, Workflow
from agent_framework_orchestrations import HandoffBuilder, HandoffSentEvent

from polymath.agents import create_coordinator, create_info_specialist, create_math_specialist
from polymath.client import build_chat_client
from polymath.utils import format_agent_workflow, format_tool_chain

logger = logging.getLogger(__name__)


def build_workflow() -> Workflow:
    """Construct the compiled multi-agent handoff workflow.

    Returns:
        A :class:`agent_framework.Workflow` ready to ``await workflow.run(...)``.
    """
    client = build_chat_client()
    coordinator = create_coordinator(client)
    math_specialist = create_math_specialist(client)
    info_specialist = create_info_specialist(client)

    workflow = (
        HandoffBuilder(
            name="polymath_handoff",
            participants=[coordinator, math_specialist, info_specialist],
            description=(
                "Polymath demo: coordinator routes to math / info specialists "
                "and synthesises the final answer."
            ),
        )
        .with_start_agent(coordinator)
        .add_handoff(coordinator, [math_specialist, info_specialist])
        .add_handoff(math_specialist, [coordinator])
        .add_handoff(info_specialist, [coordinator])
        # Cap autonomous turns so the workflow always terminates even if a
        # specialist forgets to hand back. Coordinator gets the highest budget
        # because it does the orchestration.
        .with_autonomous_mode(
            turn_limits={
                "coordinator": 8,
                "math_specialist": 4,
                "info_specialist": 4,
            },
        )
        .build()
    )
    return workflow


# ---------------------------------------------------------------------------
# Result shaping
# ---------------------------------------------------------------------------


def _coerce_args(arguments: Any) -> dict[str, Any]:
    """Coerce a MAF ``function_call`` ``arguments`` payload into a plain dict.

    MAF carries the model's tool arguments either as a JSON string (the
    OpenAI-compat path streams it that way) or as an already-decoded
    ``dict``. Wrap any other shape in a single-key dict so the FastAPI
    response is always JSON-serialisable.
    """
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        import json

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
    """Pull tool invocations out of a single :class:`AgentResponseUpdate`.

    MAF's :class:`HandoffBuilder` workflow streams one ``output`` event per
    :class:`AgentResponseUpdate`, where the update is a delta from one agent
    (identified by ``author_name``). When that delta carries the model's
    tool-call decision, ``contents`` contains a ``Content`` instance with
    ``type == "function_call"`` and ``role == "assistant"``. We deliberately
    skip the auto-injected ``handoff_to_*`` tools here so only domain tools
    show up in the chain returned to the API caller.
    """
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


def _capture_final_text(request_info_data: Any, *, fallback: list[str]) -> str | None:
    """Pull the synthesised final answer out of a ``request_info`` event.

    In MAF's handoff workflow, the coordinator's final answer is delivered
    as :class:`HandoffAgentUserRequest.agent_response`, NOT as a ``list``
    payload on the ``output`` event (the previous version of this code
    expected the latter and never matched). Falls back to the most recent
    streamed assistant text if the request_info shape ever changes.
    """
    agent_response = getattr(request_info_data, "agent_response", None)
    text = getattr(agent_response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    if fallback:
        joined = "\n".join(t for t in fallback if t).strip()
        return joined or None
    return None


def _normalize_agent_order(agents_seen: list[str], handoff_targets: list[str]) -> list[str]:
    """Build the ordered, deduped list of agents that participated.

    Combines the agents observed in the streamed updates with the explicit
    handoff destinations from ``handoff_sent`` events so the very first
    coordinator response is never missed if the model handed off before
    producing text.
    """
    ordered: list[str] = []
    if "coordinator" in agents_seen or "coordinator" in handoff_targets:
        ordered.append("coordinator")
    for name in agents_seen:
        if name and name not in ordered:
            ordered.append(name)
    for target in handoff_targets:
        if target and target not in ordered:
            ordered.append(target)
    return ordered


# ---------------------------------------------------------------------------
# Invocation
# ---------------------------------------------------------------------------


async def invoke_polymath_async(
    workflow: Workflow,
    user_message: str,
    *,
    conversation_history: list[Message] | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Run the workflow once and return a structured result.

    Stream-driven by design: MAF's :class:`HandoffBuilder` workflow does not
    emit a single ``output`` event with the final ``list[Message]``. It
    streams one ``output`` event per :class:`AgentResponseUpdate` (per-agent
    delta) and encodes the synthesised answer in a ``request_info`` event
    carrying a :class:`HandoffAgentUserRequest`. We accumulate tool calls
    and agent participation from the update stream and pull the final text
    from the request_info payload.

    Args:
        workflow: The compiled handoff workflow from :func:`build_workflow`.
        user_message: The user's question to send to the coordinator.
        conversation_history: Optional list of prior :class:`Message` objects
            from earlier turns. When provided we feed the history + the new
            message in as a list so the agents have full context.
        conversation_id: Optional caller-provided conversation id; passed
            through verbatim into the result for the FastAPI layer to track.

    Returns:
        Dict with ``response``, ``messages``, ``tools_called``,
        ``agents_involved``, ``agent_workflow``, ``tool_chain``,
        ``conversation_id``.
    """
    handoff_targets: list[str] = []
    tools_called: list[dict[str, Any]] = []
    agents_seen: list[str] = []
    streamed_assistant_text: list[str] = []
    final_text: str | None = None
    final_messages: list[Message] = []

    if conversation_history:
        # HandoffAgentExecutor (subclass of AgentExecutor) accepts
        # ``list[str | Message]`` as input -- see ``from_messages`` handler.
        workflow_input: Any = [*conversation_history, Message("user", [user_message])]
    else:
        workflow_input = user_message

    async for event in workflow.run(workflow_input, stream=True):
        event_type = getattr(event, "type", None)
        data = getattr(event, "data", None)

        if event_type == "handoff_sent" and isinstance(data, HandoffSentEvent):
            handoff_targets.append(data.target)
            continue

        if event_type == "output" and data is not None:
            # MAF streams an AgentResponseUpdate per per-agent delta. Each
            # update can carry text deltas, function_call deltas, or
            # function_result deltas; we record tool calls + author here and
            # also keep any non-empty assistant text as a fallback for
            # ``response``.
            _record_function_calls(data, tools_called=tools_called, agents_seen=agents_seen)
            if getattr(data, "role", None) == "assistant":
                text = (getattr(data, "text", "") or "").strip()
                if text:
                    streamed_assistant_text.append(text)
                    msg = Message(
                        role="assistant",
                        contents=[
                            c
                            for c in (getattr(data, "contents", None) or [])
                            if getattr(c, "type", None) == "text"
                        ],
                        author_name=getattr(data, "author_name", None),
                    )
                    final_messages.append(msg)
            continue

        if event_type == "request_info":
            captured = _capture_final_text(data, fallback=streamed_assistant_text)
            if captured:
                final_text = captured
                # Also surface the coordinator's final assistant message so
                # downstream code that wants the conversation list has at
                # least the synthesised answer.
                ar_messages = getattr(getattr(data, "agent_response", None), "messages", None) or []
                if ar_messages:
                    final_messages = list(ar_messages)
            continue

    response_text = (
        final_text
        if final_text is not None
        else "\n".join(t for t in streamed_assistant_text if t).strip()
    )
    agents_involved = _normalize_agent_order(agents_seen, handoff_targets)

    return {
        "response": response_text,
        "messages": final_messages,
        "tools_called": tools_called,
        "agents_involved": agents_involved,
        "agent_workflow": format_agent_workflow(agents_involved),
        "tool_chain": format_tool_chain(tools_called),
        "conversation_id": conversation_id,
    }


def invoke_polymath(
    workflow: Workflow,
    user_message: str,
    *,
    conversation_history: list[Message] | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Sync wrapper around :func:`invoke_polymath_async`.

    Lets the FastAPI ``@endpoint``-decorated handler stay sync (matches the
    surface used by ``agents/research-assistant``).

    Note: must be called from a thread that does not already have a running
    event loop. FastAPI's threadpool execution path satisfies this.
    """
    return asyncio.run(
        invoke_polymath_async(
            workflow,
            user_message,
            conversation_history=conversation_history,
            conversation_id=conversation_id,
        )
    )


# ---------------------------------------------------------------------------
# Convenience for the example CLI
# ---------------------------------------------------------------------------


async def run_query(query: str) -> dict[str, Any]:
    """Build a fresh workflow and run a single query. Useful for the CLI demo."""
    workflow = build_workflow()
    return await invoke_polymath_async(workflow, query)


def get_participants(workflow: Workflow) -> list[Agent]:
    """Return the participating ``Agent`` instances on a built workflow.

    Best-effort accessor used by the FastAPI ``/health`` endpoint to confirm
    the workflow was built with the expected agents. Returns an empty list if
    introspection fails (which can happen across MAF versions).
    """
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
