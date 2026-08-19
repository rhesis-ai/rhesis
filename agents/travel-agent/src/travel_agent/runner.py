"""Running one conversation turn.

The shape of a turn: classify the message, decide whether it even needs the model, run
this turn's workflow with the brief bound, then resolve exactly one reply. The reply is
never scraped out of whatever prose happened to survive - it is either a terminal tool's
output or the coordinator's own text, both of which are unambiguous.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agent_framework import Message

from travel_agent.brief import bind_brief
from travel_agent.safety import SafetyAction, classify, refusal_for
from travel_agent.state import (
    Phase,
    TripBrief,
    derive_phase,
    render_plan,
)
from travel_agent.utils import (
    assistant_message,
    collect_segment,
    coordinator_text,
    format_agent_workflow,
    format_tool_chain,
    normalize_agent_order,
    record_function_calls,
    user_message,
)
from travel_agent.workflow import build_travel_workflow

logger = logging.getLogger(__name__)

TURN_TIMEOUT_SECONDS = 90
# A full build fans out to at most six specialists; anything past this is a routing loop.
# Exceeding it stops the turn being *recorded*, not running - the timeout is the hard stop.
MAX_HANDOFFS = 14


class TurnFailedError(RuntimeError):
    """The turn produced no reply at all. A wiring bug, not a degraded service."""


def _blocked_turn(brief: TripBrief, message: str, reply: str) -> dict[str, Any]:
    """A refusal, served without touching the model."""
    logger.info("Blocked out-of-scope or injection attempt; replying without running the workflow")
    return _result(
        brief,
        message,
        reply,
        tools_called=[],
        agents_involved=[],
        handoffs=[],
    )


def _result(
    brief: TripBrief,
    message: str,
    reply: str,
    *,
    tools_called: list[dict[str, Any]],
    agents_involved: list[str],
    handoffs: list[str],
    history: list[Message] | None = None,
) -> dict[str, Any]:
    messages = [*(history or []), user_message(message), assistant_message(reply)]
    return {
        "response": reply,
        "messages": messages,
        "brief": brief,
        "phase": derive_phase(brief).value,
        "degraded_services": sorted(brief.unavailable),
        "tools_called": tools_called,
        "agents_involved": agents_involved,
        "agent_workflow": format_agent_workflow(agents_involved),
        "tool_chain": format_tool_chain(tools_called),
        "handoffs": handoffs,
    }


async def run_turn(
    brief: TripBrief,
    message: str,
    *,
    conversation_history: list[Message] | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Run one turn against ``brief``, mutating it in place."""
    brief.turn += 1
    brief.pending_reply = None
    brief.last_user_message = message

    verdict = classify(message, brief)
    if verdict.blocked:
        return _blocked_turn(brief, message, refusal_for(verdict))

    handoffs: list[str] = []
    tools_called: list[dict[str, Any]] = []
    agents_seen: list[str] = []
    segments: list[dict[str, Any]] = []
    hop_budget_hit = False

    with bind_brief(brief):
        workflow = build_travel_workflow(
            brief,
            message,
            verdict=verdict if verdict.action is SafetyAction.FLAG else None,
            client=client,
        )
        workflow_input = [*(conversation_history or []), user_message(message)]

        async def _consume() -> None:
            nonlocal hop_budget_hit
            async for event in workflow.run(workflow_input, stream=True):
                if hop_budget_hit:
                    # Keep draining rather than breaking out. Abandoning the stream mid-flight
                    # closes MAF's async generator from the wrong context and OTEL fails to
                    # detach its span token, which buries the real problem in a traceback.
                    continue

                event_type = getattr(event, "type", None)
                data = getattr(event, "data", None)

                if event_type == "handoff_sent" and data is not None:
                    handoffs.append(getattr(data, "target", "") or "")
                    if len(handoffs) > MAX_HANDOFFS:
                        logger.warning("Hop budget of %d handoffs exceeded", MAX_HANDOFFS)
                        hop_budget_hit = True
                elif event_type == "output" and data is not None:
                    record_function_calls(data, tools_called=tools_called, agents_seen=agents_seen)
                    collect_segment(data, segments)

        try:
            await asyncio.wait_for(_consume(), timeout=TURN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            # Not fatal: the specialists write straight into the brief, so a turn that
            # runs long still leaves everything they found behind to answer from.
            logger.warning("Turn exceeded %ss; answering from the brief", TURN_TIMEOUT_SECONDS)
            hop_budget_hit = True

    reply = _resolve_reply(brief, segments, hop_budget_hit=hop_budget_hit)
    agents_involved = normalize_agent_order(agents_seen, handoffs)
    return _result(
        brief,
        message,
        reply,
        tools_called=tools_called,
        agents_involved=agents_involved,
        handoffs=handoffs,
        history=conversation_history,
    )


def _resolve_reply(
    brief: TripBrief,
    segments: list[dict[str, Any]],
    *,
    hop_budget_hit: bool,
) -> str:
    """Pick the one thing the user sees.

    A terminal tool wins outright - it was called precisely to end the turn. Otherwise the
    coordinator's own text is the reply. Only when neither exists do we fall back to
    rendering the brief ourselves, which is what keeps a stalled turn useful.
    """
    if brief.pending_reply:
        reply = brief.pending_reply
        brief.pending_reply = None
        return reply

    text = coordinator_text(segments)
    if text:
        if derive_phase(brief) in (Phase.BUILDING, Phase.PLANNED):
            brief.plan_text = text
        return text

    if brief.legs:
        logger.warning(
            "Coordinator produced no reply (hop budget hit: %s); rendering the plan from the brief",
            hop_budget_hit,
        )
        plan = render_plan(brief)
        brief.plan_text = plan
        return plan

    raise TurnFailedError(
        "The coordinator produced no reply and the brief holds nothing to answer from. "
        f"Agents seen: {[segment.get('author') for segment in segments]}"
    )


__all__ = [
    "MAX_HANDOFFS",
    "TURN_TIMEOUT_SECONDS",
    "TurnFailedError",
    "run_turn",
]
