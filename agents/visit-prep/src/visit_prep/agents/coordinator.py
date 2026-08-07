"""Coordinator Agent that routes intents and hands off to specialists.

No ``from __future__ import annotations`` here on purpose — see ``agents/summary.py``.
"""

from haystack.components.agents import Agent, State
from haystack.components.generators.chat.types import ChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.hooks import hook
from haystack.tools import Tool

from visit_prep.agents.history import create_history_agent
from visit_prep.agents.summary import create_summary_agent, run_summary_with_fallback
from visit_prep.safety import first_red_flag_text
from visit_prep.state import describe_slots, missing_core_slots, state_from_slots
from visit_prep.tools import build_red_flag_tool, build_terminal_tools
from visit_prep.utils import as_text, conversation_messages

# `slot_status` is rendered in by the turn layer: Agent State never reaches the model, so
# without it the coordinator cannot tell whether the history is complete.
COORDINATOR_SYSTEM_PROMPT = """\
You are Visit-Prep, a coordinator that helps users prepare for a doctor's appointment. \
You never diagnose or recommend treatment.

What is already on file for this conversation:
{{ slot_status }}

On EVERY turn, follow this order strictly:
1. Call check_red_flags (it takes no arguments — it reads the latest user message itself).
2. If it reports RED_FLAG_DETECTED, call escalate immediately and stop.
3. Otherwise choose exactly one path:
   - greet_and_explain — for greetings or questions about what you do
   - redirect_to_scope — if the user asks for a diagnosis, medication, or treatment
   - gather_history — if the user describes a symptom or answers a history question
   - write_summary — when the notes above say the history is complete, or when \
gather_history reports HISTORY_COMPLETE

gather_history returns the next question to ask; reply to the user with that question in your \
own closing message. write_summary returns a reviewed summary; reply with it unchanged. Never \
show the user a tool's internal status line (anything starting with HISTORY_COMPLETE, \
SUMMARY_BLOCKED, or VERDICT) — those are instructions for you, not answers for the user.
"""

COORDINATOR_STATE_SCHEMA = {
    "slots": {"type": dict},
    "chief_complaint": {"type": str},
    # Written by write_summary once the critic has approved; the turn layer reads it back as
    # the user-facing reply, so an approved summary cannot be paraphrased on the way out.
    "summary": {"type": str},
    # Set by the red-flag hook so the override is injected once per run, and so the turn
    # layer can record that a rule match happened even if the model ignored it.
    "red_flag_warned": {"type": bool},
}

# Tools that end the run the moment they are called, because their return value *is* the
# user-facing reply. Handoffs are deliberately absent: the coordinator must see what a
# specialist returned so it can decide what comes next.
TERMINAL_TOOLS = ("escalate", "greet_and_explain", "redirect_to_scope")

# Status lines tools return to steer the coordinator. The system prompt above asks the model
# never to show one to the user, but a prompt is not an enforcement mechanism, and two paths
# reach the user without the model misbehaving at all: a run that stops on ``max_agent_steps``
# leaves a handoff's tool result as the last message, and a model that parrots the line back
# as its closing text ends the run on it. The turn layer refuses both.
INTERNAL_STATUS_PREFIXES = ("HISTORY_COMPLETE", "SUMMARY_BLOCKED", "VERDICT")


def is_internal_status(text: str) -> bool:
    """True when ``text`` is a tool status line meant for the coordinator, not the user."""
    return text.lstrip().startswith(INTERNAL_STATUS_PREFIXES)


RED_FLAG_OVERRIDE = (
    "SAFETY OVERRIDE: a rule-based scan matched potentially urgent symptoms in the user's "
    "own words ({flagged!r}). Call escalate now and do not call any other tool."
)


@hook
def red_flag_guard(state: State) -> None:
    """Run the red-flag rules on every step, whatever the model chooses to call.

    ``check_red_flags`` is an ordinary tool, so a coordinator that never calls it would never
    be checked. This hook closes that hole: it scans the user's own words before each LLM call
    and injects a system instruction when the rules match.
    """
    if state.get("red_flag_warned"):
        return
    flagged = first_red_flag_text(state.get("messages") or [])
    if flagged is None:
        return
    state.set("red_flag_warned", True)
    # `State.set` merges through the schema handler rather than assigning, and Haystack always
    # installs `merge_lists` for `messages`, so this *appends* the override. The user's own
    # words stay in the history, which `check_red_flags` still needs to read. Reads as a
    # destructive overwrite otherwise, and swapping in an explicit prepend would duplicate the
    # entire history instead of reordering it.
    state.set("messages", [ChatMessage.from_system(RED_FLAG_OVERRIDE.format(flagged=flagged))])


def create_coordinator_agent(generator: ChatGenerator) -> Agent:
    """Build the coordinator with terminal tools and specialist handoffs."""
    history_agent = create_history_agent(generator)
    summary_agent = create_summary_agent(generator)

    def gather_history(message: str, state: State) -> str:
        """Delegate symptom-history gathering to the history specialist."""
        # The parameter is declared as a string, but the model answers a severity question
        # with a bare `9` often enough that the argument arrives as a JSON number.
        text = as_text(message)
        before = state_from_slots(state.get("chief_complaint"), state.get("slots") or {})

        # Forward the conversation so far, so the specialist can tell which slot a short
        # answer like "9" belongs to and does not re-ask what it already asked.
        prior = conversation_messages(state.get("messages") or [])
        if prior and as_text(prior[-1].text).strip() == text.strip():
            prior = prior[:-1]

        result = history_agent.run(
            messages=[*prior, ChatMessage.from_user(text)],
            slots=before.slots.model_dump(),
            chief_complaint=before.chief_complaint or "",
            slot_status=describe_slots(before),
        )
        if isinstance(result.get("slots"), dict):
            state.set("slots", result["slots"])
        if result.get("chief_complaint"):
            state.set("chief_complaint", result["chief_complaint"])

        after = state_from_slots(state.get("chief_complaint"), state.get("slots") or {})
        if missing_core_slots(after):
            return result["last_message"].text or "Ask the user for the next missing detail."
        return (
            "HISTORY_COMPLETE — every core slot is now filled. Call write_summary next; "
            "do not ask another question."
        )

    def write_summary(state: State) -> str:
        """Delegate summary writing + safety review when history is complete."""
        visit_state = state_from_slots(state.get("chief_complaint"), state.get("slots") or {})
        missing = missing_core_slots(visit_state)
        if missing:
            return (
                f"SUMMARY_BLOCKED — core slots still missing: {', '.join(missing)}. "
                "Call gather_history with the latest user message instead."
            )
        text = run_summary_with_fallback(summary_agent, state=visit_state)
        state.set("summary", text)
        return text

    handoff_tools = [
        Tool(
            name="gather_history",
            description=(
                "Hand off to the history specialist to extract symptom slots and ask the "
                "next question. Pass the latest user message."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The latest user message about their symptoms.",
                    },
                },
                "required": ["message"],
            },
            function=gather_history,
        ),
        Tool(
            name="write_summary",
            description=(
                "Hand off to the summary specialist to produce the visit-prep timeline and "
                "clinician questions once all core slots are filled. Takes no arguments."
            ),
            parameters={"type": "object", "properties": {}},
            function=write_summary,
        ),
    ]

    return Agent(
        chat_generator=generator,
        tools=[build_red_flag_tool(), *build_terminal_tools(), *handoff_tools],
        system_prompt=COORDINATOR_SYSTEM_PROMPT,
        state_schema=COORDINATOR_STATE_SCHEMA,
        exit_conditions=["text", *TERMINAL_TOOLS],
        max_agent_steps=10,
        hooks={"before_llm": [red_flag_guard]},
    )


__all__ = [
    "COORDINATOR_STATE_SCHEMA",
    "COORDINATOR_SYSTEM_PROMPT",
    "INTERNAL_STATUS_PREFIXES",
    "RED_FLAG_OVERRIDE",
    "TERMINAL_TOOLS",
    "create_coordinator_agent",
    "is_internal_status",
    "red_flag_guard",
]
