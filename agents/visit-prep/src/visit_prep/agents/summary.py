"""Summary-writer specialist Agent with critic handoff.

No ``from __future__ import annotations`` here on purpose: Haystack injects the live Agent
``State`` by comparing the raw parameter annotation against the ``State`` class, so postponed
annotations turn it into the string ``"State"`` and the injection silently stops happening.
The same applies to ``tools.py`` and ``agents/coordinator.py``.
"""

from haystack.components.agents import Agent, State
from haystack.components.generators.chat.types import ChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools import Tool

from visit_prep.agents.critic import create_critic_agent
from visit_prep.state import VisitPrepState

SUMMARY_SYSTEM_PROMPT = """\
Using ONLY the information in the provided slots, write a short visit-prep summary: a \
chronological timeline of the symptom, then a brief list of questions the user could ask \
their doctor. Do not add any symptom, cause, or possibility the user did not state. Do not \
diagnose or suggest treatment.

After drafting (or rewriting) the summary, call review_summary with the full draft text. \
If the review is rejected, rewrite once using the feedback and call review_summary again.

Your final text reply must be the approved summary itself, nothing else.
"""

# `review_summary` mirrors the critic's decision here so the wrapper below can enforce it.
SUMMARY_STATE_SCHEMA = {
    "approved": {"type": bool},
    "approved_summary": {"type": str},
}


def _fallback_summary(slots: dict[str, str | None], chief_complaint: str | None) -> str:
    """Deterministic slot recap used when no summary draft earned the critic's approval."""
    labels = {
        "onset": "Started",
        "location": "Location",
        "character": "What it feels like",
        "severity": "Severity",
        "timing": "Pattern",
        "aggravating": "Makes it worse",
        "relieving": "Makes it better",
        "associated": "Other symptoms",
        "context": "Background",
    }
    lines = ["Here is a recap of what you've told me, to bring to your appointment:", ""]
    if chief_complaint:
        lines.append(f"Main concern: {chief_complaint}")
    for slot_name, label in labels.items():
        value = slots.get(slot_name) if isinstance(slots, dict) else None
        if value:
            lines.append(f"- {label}: {value}")
    lines += [
        "",
        "Questions you could ask your clinician:",
        "- What might explain these symptoms, and what would you want to check first?",
        "- Are there warning signs that should bring me back sooner?",
        "- Is there anything I can safely do to manage this in the meantime?",
    ]
    return "\n".join(lines)


def create_summary_agent(generator: ChatGenerator) -> Agent:
    """Build the summary writer that hands off to the critic for review."""
    critic = create_critic_agent(generator)

    def review_summary(summary: str, state: State) -> str:
        """Send a summary draft to the safety critic for approval."""
        result = critic.run(
            messages=[
                ChatMessage.from_user(
                    "Review this visit-prep summary for safety and grounding:\n\n" + summary
                )
            ]
        )
        approved = bool(result.get("approved"))
        state.set("approved", approved)
        if approved:
            state.set("approved_summary", summary)
            return "VERDICT: approved. Reply to the user with this summary, unchanged."
        feedback = result.get("feedback") or "Rewrite without diagnosis or treatment."
        return f"VERDICT: rejected. Feedback: {feedback}"

    review_tool = Tool(
        name="review_summary",
        description="Send a summary draft to the independent safety critic for approval.",
        parameters={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "The full visit-prep summary draft to review.",
                },
            },
            "required": ["summary"],
        },
        function=review_summary,
    )

    return Agent(
        chat_generator=generator,
        tools=[review_tool],
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        state_schema=SUMMARY_STATE_SCHEMA,
        exit_conditions=["text"],
        max_agent_steps=8,
    )


def run_summary_with_fallback(summary_agent: Agent, *, state: VisitPrepState) -> str:
    """Run the summary agent, returning only text the critic actually approved.

    The approved draft is taken from Agent State, not from the model's closing message, so
    an unreviewed or rewritten-after-approval reply cannot reach the user. With no approval
    at all we ship the deterministic recap instead.
    """
    slots = state.slots.model_dump()
    prompt = f"Chief complaint: {state.chief_complaint or '(not recorded)'}\nSlots:\n" + "\n".join(
        f"- {k}: {v if v is not None else '(missing)'}" for k, v in slots.items()
    )
    result = summary_agent.run(messages=[ChatMessage.from_user(prompt)])
    if result.get("approved") and result.get("approved_summary"):
        return str(result["approved_summary"])
    return _fallback_summary(slots, state.chief_complaint)


__all__ = [
    "SUMMARY_STATE_SCHEMA",
    "SUMMARY_SYSTEM_PROMPT",
    "_fallback_summary",
    "create_summary_agent",
    "run_summary_with_fallback",
]
