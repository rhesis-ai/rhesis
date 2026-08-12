"""ADK Runner wrapping the Reg-Advisor coordinator agent for one conversation turn.

This is the analogue of visit-prep's ``pipeline.py``: build the coordinator, run one turn,
extract the reply, produce the new domain state.

ADK's session service and :class:`RegAdvisorState` are two different things and are kept that
way. Each turn seeds a fresh ADK session from the domain state and reads the final state back
out; ADK's own session records are scratch space for one invocation, not the store of record.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from reg_advisor.agents.coordinator import STEP_BUDGET, create_coordinator_agent, is_internal_status
from reg_advisor.client import build_model
from reg_advisor.state import Phase, RegAdvisorState, profile_from_state
from reg_advisor.terminals import refer_to_expert
from reg_advisor.utils import as_text, clip, user_texts

APP_NAME = "reg_advisor"
USER_ID = "reg-advisor-user"

# One turn's worth of user text. A 10k-character paste would otherwise swamp every prompt in the
# nested run, including the specialists'.
MAX_MESSAGE_CHARS = 8000


def build_coordinator_agent(model: Any = None) -> LlmAgent:
    """Build the coordinator, sharing one model with its specialists."""
    return create_coordinator_agent(model or build_model())


def build_runner(model: Any = None) -> Runner:
    """Build an ADK runner around the coordinator, with its own in-memory session service."""
    return Runner(
        app_name=APP_NAME,
        agent=build_coordinator_agent(model),
        session_service=InMemorySessionService(),
    )


def _seed_state(message: str, state: RegAdvisorState) -> dict[str, Any]:
    """The ADK session state one turn starts from.

    ``user_turns`` carries every user turn in the replayed conversation plus this one. Both the
    scope tool and the scope callback read it, which is what makes referral sticky: a flag
    raised on an earlier turn keeps matching.
    """
    return {
        "turn": state.turn,
        "phase": state.phase.value,
        "profile": state.profile.model_dump(),
        "history": list(state.history),
        "determinations": list(state.determinations),
        "scope_flag": state.scope_flag,
        "user_turns": [*user_texts(state.history), message],
    }


def _new_message(message: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=message)])


def _tool_call_counts(events: list[Event]) -> dict[str, int]:
    """How many times each tool was called. ADK does not provide this, so count the events.

    Coordinator-level calls only. ``AgentTool`` runs each specialist in its own ``Runner``, so a
    nested ``record_profile`` or ``submit_verdict`` never reaches this event stream. What a
    specialist did shows up in the state it wrote back, not here.
    """
    counts: dict[str, int] = {}
    for event in events:
        for call in event.get_function_calls():
            counts[call.name] = counts.get(call.name, 0) + 1
    return counts


def _final_texts(events: list[Event]) -> list[str]:
    return [
        part.text
        for event in events
        if event.is_final_response() and event.content and event.content.parts
        for part in event.content.parts
        if part.text
    ]


def _extract_reply(result: dict[str, Any]) -> str:
    """Return the user-facing reply for one coordinator run, or ``""`` if there is none.

    Precedence is deliberate. A terminal tool wins over everything, because a referral must not
    be buried under a briefing the model wrote earlier in the same run. Then the critic-approved
    briefing, so the reviewed text reaches the user verbatim rather than paraphrased. Only then
    the model's own closing text.

    An internal status line is never a reply, however it turns up: an exhausted step budget
    leaves a handoff's tool result as the last message, and a model that echoes the line back
    ends the run on it. Both are refused here, so the turn fails loudly in :func:`_finish_turn`
    rather than handing the user a tool's instructions.
    """
    terminal = as_text(result.get("terminal_reply"))
    if terminal:
        return terminal

    # A flag was raised and no terminal tool ran, so the model ignored the injected override.
    # The rules decide the turn, not the model: without this, the one path around the scope
    # check is simply declining to act on it.
    if result.get("scope_flag"):
        return refer_to_expert()

    briefing = as_text(result.get("briefing"))
    if briefing and not is_internal_status(briefing):
        return briefing

    for candidate in reversed(result.get("final_texts") or []):
        text = as_text(candidate).strip()
        if text and not is_internal_status(text):
            return text
    return ""


def _apply_result_to_state(
    state: RegAdvisorState,
    result: dict[str, Any],
    reply: str,
    user_message: str,
) -> RegAdvisorState:
    updated = state.model_copy(deep=True)
    updated.turn += 1
    updated.history = [
        *updated.history,
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": reply},
    ]
    updated.profile = profile_from_state(result.get("profile"))
    updated.determinations = list(result.get("determinations") or updated.determinations)

    # Phase follows what actually happened, not merely which tools were called: a blocked
    # write_briefing leaves no briefing behind and must not read as "briefed".
    counts: dict[str, int] = result.get("tool_call_counts") or {}
    if result.get("scope_flag"):
        updated.scope_flag = True
    if counts.get("refer_to_expert") or result.get("scope_flag"):
        updated.phase = Phase.REFERRED
    elif result.get("briefing"):
        updated.phase = Phase.BRIEFED
    elif result.get("determinations"):
        updated.phase = Phase.CLASSIFIED
    elif counts.get("gather_profile"):
        updated.phase = Phase.SCOPING
    return updated


def _finish_turn(state: RegAdvisorState, result: dict[str, Any], message: str) -> dict[str, Any]:
    reply = _extract_reply(result)
    if not reply:
        raise RuntimeError(f"Coordinator completed without a user-facing reply: {sorted(result)}")
    return {
        "response": reply,
        "state": _apply_result_to_state(state, result, reply, message),
        "raw": result,
    }


async def _collect(
    runner: Runner,
    message: str,
    state: RegAdvisorState,
) -> dict[str, Any]:
    """Run one turn and gather everything the turn layer needs from it.

    ``LlmCallsLimitExceededError`` is caught rather than propagated: ADK raises it mid-stream
    after events have already been yielded, and the events collected so far still hold a usable
    reply — or, if they do not, `_finish_turn` fails loudly on our terms instead of on ADK's.
    """
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, state=_seed_state(message, state)
    )
    events: list[Event] = []
    budget_exhausted = False
    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session.id,
            new_message=_new_message(message),
            run_config=RunConfig(max_llm_calls=STEP_BUDGET),
        ):
            events.append(event)
    except LlmCallsLimitExceededError:
        budget_exhausted = True

    final = await runner.session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session.id
    )
    return {
        **dict(final.state if final else {}),
        "events": events,
        "final_texts": _final_texts(events),
        "tool_call_counts": _tool_call_counts(events),
        "budget_exhausted": budget_exhausted,
    }


async def run_turn_async(
    message: str,
    state: RegAdvisorState | None = None,
    *,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Run one conversation turn through the coordinator.

    ``as_text`` is the boundary for the whole turn: an HTTP client can send a bare JSON number,
    and everything downstream — the scope regexes, the profile slots, the classifier's keyword
    checks — assumes text.
    """
    current = state or RegAdvisorState()
    text = clip(as_text(message), MAX_MESSAGE_CHARS)
    active = runner or build_runner()
    result = await _collect(active, text, current)
    return _finish_turn(current, result, text)


def run_turn(
    message: str,
    state: RegAdvisorState | None = None,
    *,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Synchronous variant of :func:`run_turn_async`.

    ADK's own sync ``Runner.run`` is documented as being for local testing, so the sync path
    drives the async one on a private event loop instead. Same code, one behaviour to reason
    about.
    """
    return asyncio.run(run_turn_async(message, state, runner=runner))


def new_conversation_id() -> str:
    return str(uuid.uuid4())


__all__ = [
    "APP_NAME",
    "MAX_MESSAGE_CHARS",
    "USER_ID",
    "build_coordinator_agent",
    "build_runner",
    "new_conversation_id",
    "run_turn",
    "run_turn_async",
]
