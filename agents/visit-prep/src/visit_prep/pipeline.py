"""Thin Haystack pipeline wrapping the Visit-Prep coordinator Agent."""

from __future__ import annotations

from typing import Any

from haystack import Pipeline
from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage, ChatRole

from visit_prep.agents.coordinator import create_coordinator_agent, is_internal_status
from visit_prep.client import build_chat_generator
from visit_prep.state import Phase, Slots, VisitPrepState, describe_slots
from visit_prep.utils import as_text, tool_result_text

COORDINATOR = "coordinator"


def build_coordinator_agent(generator=None) -> Agent:
    """Build the coordinator Agent, sharing one chat generator with its specialists."""
    return create_coordinator_agent(generator or build_chat_generator())


def build_coordinator_pipeline(generator=None) -> Pipeline:
    """Wrap the coordinator in a one-component pipeline, for the root tracing spans."""
    pipe = Pipeline()
    pipe.add_component(COORDINATOR, build_coordinator_agent(generator))
    return pipe


def _history_to_chat_messages(history: list[dict[str, str]]) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    for item in history:
        content = as_text(item.get("content", ""))
        if item.get("role") == "assistant":
            messages.append(ChatMessage.from_assistant(content))
        else:
            messages.append(ChatMessage.from_user(content))
    return messages


def _run_data(message: str, state: VisitPrepState) -> dict[str, Any]:
    """Build the pipeline input for one turn."""
    return {
        COORDINATOR: {
            "messages": [
                *_history_to_chat_messages(state.history),
                ChatMessage.from_user(message),
            ],
            "slots": state.slots.model_dump(),
            "chief_complaint": state.chief_complaint or "",
            "slot_status": describe_slots(state),
        }
    }


def _extract_reply(result: dict[str, Any]) -> str:
    """Return the user-facing reply for one coordinator run, or ``""`` if there is none.

    A critic-approved summary wins over anything the model says afterwards, so the reviewed
    text reaches the user verbatim. Otherwise the run ended either on a terminal tool (whose
    templated result is the reply) or on a plain text reply.

    An internal status line is never a reply, however it turns up: an exhausted
    ``max_agent_steps`` budget leaves a handoff's tool result as the last message, and a model
    that echoes the line back ends the run on it. Both are refused here, so the turn fails
    loudly in :func:`_finish_turn` rather than handing the user a tool's instructions.
    """
    summary = result.get("summary")
    if summary:
        return str(summary)

    last = result.get("last_message")
    if isinstance(last, ChatMessage):
        candidate = tool_result_text(last) if last.is_from(ChatRole.TOOL) else (last.text or "")
        if candidate and not is_internal_status(candidate):
            return candidate
    return ""


def _apply_result_to_state(
    state: VisitPrepState,
    result: dict[str, Any],
    reply: str,
    user_message: str,
) -> VisitPrepState:
    updated = state.model_copy(deep=True)
    updated.turn += 1
    updated.history = [
        *updated.history,
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": reply},
    ]

    if isinstance(result.get("slots"), dict):
        updated.slots = Slots.model_validate(result["slots"])
    if result.get("chief_complaint"):
        updated.chief_complaint = result["chief_complaint"]

    # Phase follows what actually happened, not merely which tools were called: a blocked
    # write_summary leaves no approved summary behind and must not read as "done".
    counts: dict[str, int] = result.get("tool_call_counts") or {}
    if result.get("red_flag_warned"):
        updated.red_flag = True
    if counts.get("escalate"):
        updated.phase = Phase.ESCALATED
        updated.red_flag = True
    elif result.get("summary"):
        updated.phase = Phase.DONE
    elif counts.get("gather_history"):
        updated.phase = Phase.GATHERING

    return updated


def _finish_turn(state: VisitPrepState, raw: dict[str, Any], message: str) -> dict[str, Any]:
    result = raw[COORDINATOR]
    reply = _extract_reply(result)
    if not reply:
        raise RuntimeError(
            f"Coordinator completed without a user-facing reply: {list(result.keys())}"
        )
    return {
        "response": reply,
        "state": _apply_result_to_state(state, result, reply, message),
        "raw": result,
    }


def run_turn(
    message: str,
    state: VisitPrepState | None = None,
    *,
    pipeline: Pipeline | None = None,
) -> dict[str, Any]:
    """Run one conversation turn through the coordinator pipeline.

    ``as_text`` is the boundary for the whole turn: a ``ChatMessage`` does not validate its
    content, so a message that is not a string would travel all the way into the red-flag
    regexes before failing there.
    """
    current = state or VisitPrepState()
    text = as_text(message)
    pipe = pipeline or build_coordinator_pipeline()
    raw = pipe.run(data=_run_data(text, current))
    return _finish_turn(current, raw, text)


async def run_turn_async(
    message: str,
    state: VisitPrepState | None = None,
    *,
    pipeline: Pipeline | None = None,
) -> dict[str, Any]:
    """Async variant of :func:`run_turn`, sharing its input and result handling."""
    current = state or VisitPrepState()
    text = as_text(message)
    pipe = pipeline or build_coordinator_pipeline()
    raw = await pipe.run_async(data=_run_data(text, current))
    return _finish_turn(current, raw, text)


__all__ = [
    "COORDINATOR",
    "build_coordinator_agent",
    "build_coordinator_pipeline",
    "run_turn",
    "run_turn_async",
]
