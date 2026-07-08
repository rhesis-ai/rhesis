"""Safety critic subagent."""

from __future__ import annotations

from haystack import component
from haystack.dataclasses import ChatMessage
from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator
from pydantic import BaseModel

from dr_rhesis.state import DrRhesisState
from dr_rhesis.utils import extract_json_object, format_slots, reply_text

PROMPT = """You review a visit-prep summary before it reaches the user. Return ONLY JSON: \
{"approved": bool, "feedback": "<string>"}. Reject if the summary names a likely diagnosis, \
ranks possibilities, suggests treatment or medication, includes any fact not present in the \
provided state, or formats an apparent emergency as routine visit-prep. If you reject, give \
specific, actionable feedback for a single rewrite."""


class CriticVerdict(BaseModel):
    approved: bool
    feedback: str = ""


@component
class SafetyCritic:
    """Adversarial reviewer with veto power over the summary."""

    def __init__(self, generator: GoogleGenAIChatGenerator) -> None:
        self._generator = generator

    @component.output_types(approved=bool, feedback=str)
    def run(self, summary: str, state: DrRhesisState) -> dict[str, object]:
        messages = [
            ChatMessage.from_system(PROMPT),
            ChatMessage.from_user(
                f"State slots:\n{format_slots(state.slots.model_dump())}\n"
                f"Chief complaint: {state.chief_complaint or '(not recorded)'}\n\n"
                f"Summary to review:\n{summary}"
            ),
        ]
        result = self._generator.run(messages=messages)
        payload = extract_json_object(reply_text(result["replies"]))
        verdict = CriticVerdict.model_validate(payload)
        return {"approved": verdict.approved, "feedback": verdict.feedback}


def create_safety_critic(generator: GoogleGenAIChatGenerator) -> SafetyCritic:
    return SafetyCritic(generator=generator)


__all__ = ["PROMPT", "CriticVerdict", "SafetyCritic", "create_safety_critic"]
