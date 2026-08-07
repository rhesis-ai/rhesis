"""Tools for the Visit-Prep multi-agent system."""

from typing import Any

from haystack.components.agents import State
from haystack.tools import Tool

from visit_prep.safety import text_suggests_red_flag
from visit_prep.state import CORE_SLOTS, apply_slot_updates, state_from_slots
from visit_prep.terminals import escalate, greet_and_explain, redirect_to_scope
from visit_prep.utils import as_text, latest_user_text

SLOT_NAMES = ("chief_complaint", *CORE_SLOTS, "context")

NO_MESSAGE_TO_SCAN = "No user message to scan yet. Continue with the appropriate tool."


def red_flag_report(text: str) -> str:
    """Render the rule-based red-flag verdict for one message."""
    if not text.strip():
        return NO_MESSAGE_TO_SCAN
    if text_suggests_red_flag(text):
        return (
            f"RED_FLAG_DETECTED in the user's message ({text!r}). The message describes "
            "potentially urgent symptoms. Call escalate immediately and do not continue "
            "visit preparation."
        )
    return f"No red flags detected in {text!r}. Continue with the appropriate tool."


def build_red_flag_tool() -> Tool:
    """Rule-based red-flag check over the latest user message.

    The message is read from Agent ``State`` rather than accepted as an argument: if the
    model supplied the text it could paraphrase away the very wording the patterns match.
    """

    def check_red_flags(state: State) -> str:
        return red_flag_report(latest_user_text(state.get("messages") or []))

    return Tool(
        name="check_red_flags",
        description=(
            "Scan the latest user message for emergency or red-flag symptoms. "
            "Always call this first on every turn before any other tool. Takes no arguments."
        ),
        parameters={"type": "object", "properties": {}},
        function=check_red_flags,
    )


def build_terminal_tools() -> list[Tool]:
    """Tools that end the turn with a deterministic templated response."""
    return [
        Tool(
            name="escalate",
            description="End the turn with the emergency escalation message. Use after a red flag.",
            parameters={"type": "object", "properties": {}},
            function=escalate,
        ),
        Tool(
            name="greet_and_explain",
            description="End the turn with a greeting and explanation of what Visit-Prep does.",
            parameters={"type": "object", "properties": {}},
            function=greet_and_explain,
        ),
        Tool(
            name="redirect_to_scope",
            description=(
                "End the turn with an out-of-scope redirect when the user asks for diagnosis, "
                "medication, or treatment."
            ),
            parameters={"type": "object", "properties": {}},
            function=redirect_to_scope,
        ),
    ]


def _slot_text(value: Any) -> str | None:
    """Normalise one slot value from the model, or ``None`` when it is not a usable answer.

    ``record_slots`` declares every slot as ``"type": "string"``, but a model relaying a
    severity of 9 or an onset of 2 answers with a bare JSON number often enough that
    dropping non-strings outright would lose the answer and re-ask the question. Anything
    that is not a scalar has no sensible slot text and is still dropped.
    """
    if isinstance(value, (str, int, float, bool)):
        return as_text(value)
    return None


def _merge_slots_into_state(state: State, updates: dict[str, Any]) -> str:
    """Apply slot updates to Agent State and report what is filled and what is missing."""
    candidates = ((name, _slot_text(updates.get(name))) for name in SLOT_NAMES)
    known = {name: text for name, text in candidates if text is not None}
    chief_complaint = known.pop("chief_complaint", None)

    current = state_from_slots(state.get("chief_complaint"), state.get("slots") or {})
    if chief_complaint and not current.chief_complaint:
        current = current.model_copy(deep=True)
        current.chief_complaint = chief_complaint
    current = apply_slot_updates(current, known)

    state.set("slots", current.slots.model_dump())
    if current.chief_complaint:
        state.set("chief_complaint", current.chief_complaint)

    filled = [name for name, value in current.slots.model_dump().items() if value]
    missing = [name for name in CORE_SLOTS if not getattr(current.slots, name)]
    return (
        f"Recorded slots. Filled: {', '.join(filled) or '(none)'}. "
        f"Still missing core slots: {', '.join(missing) or '(none — history complete)'}."
    )


def build_record_slots_tool() -> Tool:
    """Tool that writes OPQRST slot updates into Agent State."""

    def record_slots(state: State, **updates: Any) -> str:
        return _merge_slots_into_state(state, updates)

    properties: dict[str, Any] = {
        name: {
            "type": "string",
            "description": f"Value for {name.replace('_', ' ')} if mentioned; omit if unknown.",
        }
        for name in SLOT_NAMES
    }
    return Tool(
        name="record_slots",
        description=(
            "Record newly learned symptom history fields from the latest user message. "
            "Only include fields the user actually stated."
        ),
        parameters={"type": "object", "properties": properties, "required": []},
        function=record_slots,
    )


def build_submit_verdict_tool() -> Tool:
    """Critic exit tool: record approve/reject with feedback in Agent State.

    The verdict is written to State as a bool rather than only rendered as text, so the
    summary specialist reads a structured decision instead of parsing a sentence.
    """

    def submit_verdict(approved: bool, state: State, feedback: str = "") -> str:
        state.set("approved", bool(approved))
        state.set("feedback", feedback)
        if approved:
            return "VERDICT: approved"
        return (
            f"VERDICT: rejected. Feedback: {feedback or 'Rewrite without diagnosis or treatment.'}"
        )

    return Tool(
        name="submit_verdict",
        description=(
            "Submit your safety review of the visit-prep summary. "
            "Reject if it diagnoses, suggests treatment, or invents facts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "approved": {
                    "type": "boolean",
                    "description": "True if the summary is safe to show the user.",
                },
                "feedback": {
                    "type": "string",
                    "description": "Actionable rewrite guidance when rejecting.",
                },
            },
            "required": ["approved"],
        },
        function=submit_verdict,
    )


__all__ = [
    "SLOT_NAMES",
    "build_record_slots_tool",
    "build_red_flag_tool",
    "build_submit_verdict_tool",
    "build_terminal_tools",
    "red_flag_report",
]
