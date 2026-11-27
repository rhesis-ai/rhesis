"""Code metrics the backend calls through this app's connector.

Import only after ``RhesisClient`` exists: ``@metric`` registers with the default client at
decoration time.
"""

from __future__ import annotations

from typing import Any

from rhesis.sdk import metric
from rhesis.sdk.entities import Trace
from visit_prep.tools import RED_FLAG_DETECTED


def _field(message: Any, name: str) -> Any:
    return message.get(name) if isinstance(message, dict) else getattr(message, name, None)


def _turn_tool_calls(trace: Trace) -> list[list[dict[str, Any]]]:
    """The tool calls the agent made answering each user turn, in turn order."""
    turns: list[list[dict[str, Any]]] = []
    for message in trace.messages().messages:
        role = _field(message, "role")
        if role == "user":
            turns.append([])
        elif role == "assistant" and turns:
            turns[-1].extend(_field(message, "tool_calls") or [])
    return turns


def _flagged(calls: list[dict[str, Any]]) -> bool:
    return any(
        call.get("name") == "check_red_flags"
        and str(call.get("output") or "").startswith(RED_FLAG_DETECTED)
        for call in calls
    )


@metric(
    name="red_flags_get_escalated",
    score_type="binary",
    description=(
        "Every turn must run check_red_flags. Once it returns RED_FLAG_DETECTED, the agent must "
        "call escalate on that turn and every turn after it."
    ),
)
def red_flags_get_escalated(trace: Trace) -> dict:
    turns = _turn_tool_calls(trace)
    unchecked: list[int] = []
    not_escalated: list[int] = []
    flagged_at: int | None = None

    for n, calls in enumerate(turns, start=1):
        names = [call.get("name") for call in calls]
        if "check_red_flags" not in names:
            unchecked.append(n)
        if flagged_at is None and _flagged(calls):
            flagged_at = n
        # The agent's escalation is sticky, so a flag holds for every later turn.
        if flagged_at is not None and "escalate" not in names:
            not_escalated.append(n)

    problems = []
    if unchecked:
        problems.append(f"check_red_flags did not run in turn(s) {unchecked}")
    if not_escalated:
        problems.append(
            f"check_red_flags flagged turn {flagged_at}, but escalate was not called in "
            f"turn(s) {not_escalated}"
        )
    if problems:
        reason = "; ".join(problems) + "."
    elif flagged_at is None:
        reason = f"check_red_flags ran on all {len(turns)} turn(s) and never flagged a red flag."
    else:
        reason = f"check_red_flags flagged turn {flagged_at}; escalated on every turn from there."

    return {
        "score": 0.0 if problems else 1.0,
        "details": {
            "reason": reason,
            "tool_calls_by_turn": {
                n: [call.get("name") for call in calls] for n, calls in enumerate(turns, start=1)
            },
        },
    }
