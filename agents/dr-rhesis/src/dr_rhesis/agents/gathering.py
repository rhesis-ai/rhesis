"""Gathering brain subagent (extract + ask)."""

from __future__ import annotations

from haystack import component
from haystack.dataclasses import ChatMessage
from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator
from pydantic import BaseModel, Field

from dr_rhesis.state import CORE_SLOTS, DrRhesisState, apply_slot_updates, missing_core_slots
from dr_rhesis.utils import (
    extract_json_object,
    format_history,
    format_slots,
    normalize_slot_payload,
    reply_text,
)

PROMPT = """You help a user prepare for a doctor's visit by collecting a structured symptom \
history. You never diagnose and never suggest treatment. Given the conversation and the \
current slot state, extract any new information into the slots as JSON, then ask ONE natural \
question about the single most useful missing slot. Ask only one thing. Never re-ask something \
already answered."""


class SlotExtraction(BaseModel):
    chief_complaint: str | None = None
    onset: str | None = None
    location: str | None = None
    character: str | None = None
    severity: str | None = None
    timing: str | None = None
    aggravating: str | None = None
    relieving: str | None = None
    associated: str | None = None
    context: str | None = None


class AskResult(BaseModel):
    target_slot: str = Field(description="Name of the slot being asked about")
    question: str


EXTRACT_PROMPT = PROMPT + """

Return ONLY JSON with any newly learned fields. Include only fields mentioned in the latest \
message. Use null for unknown fields. Example shape:
{"chief_complaint": "...", "onset": "...", "location": null, ...}
"""


ASK_PROMPT = (
    PROMPT
    + """

Return ONLY JSON: {{"target_slot": "<slot_name>", "question": "<one natural question>"}}.
Pick the single most informative missing slot from this list: {missing_slots}.
Do not ask about slots that are already filled.
"""
)


@component
class GatheringBrain:
    """Extract slot updates, then ask one question about the next missing slot."""

    def __init__(self, generator: GoogleGenAIChatGenerator) -> None:
        self._generator = generator

    @component.output_types(state=DrRhesisState, question=str)
    def run(self, message: str, state: DrRhesisState) -> dict[str, object]:
        updated_state = self.extract(message, state)
        missing = missing_core_slots(updated_state)
        if not missing:
            return {"state": updated_state, "question": ""}
        question = self.ask(updated_state, missing)
        return {"state": updated_state, "question": question}

    def extract(self, message: str, state: DrRhesisState) -> DrRhesisState:
        messages = [
            ChatMessage.from_system(EXTRACT_PROMPT),
            ChatMessage.from_user(
                f"Current chief complaint: {state.chief_complaint or '(not set)'}\n"
                f"Current slots:\n{format_slots(state.slots.model_dump())}\n\n"
                f"Conversation:\n{format_history(state.history)}\n\n"
                f"Latest user message:\n{message}"
            ),
        ]
        result = self._generator.run(messages=messages)
        payload = normalize_slot_payload(extract_json_object(reply_text(result["replies"])))
        extraction = SlotExtraction.model_validate(payload)
        updates = extraction.model_dump(exclude_none=True)
        chief = updates.pop("chief_complaint", None)
        new_state = apply_slot_updates(state, updates)
        if chief and not new_state.chief_complaint:
            new_state = new_state.model_copy(deep=True)
            new_state.chief_complaint = chief
        return new_state

    def ask(self, state: DrRhesisState, missing: list[str] | None = None) -> str:
        target_missing = missing if missing is not None else missing_core_slots(state)
        if not target_missing:
            return ""
        messages = [
            ChatMessage.from_system(
                ASK_PROMPT.format(missing_slots=", ".join(target_missing))
            ),
            ChatMessage.from_user(
                f"Chief complaint: {state.chief_complaint or '(not set)'}\n"
                f"Filled slots:\n"
                f"{format_slots({k: v for k, v in state.slots.model_dump().items() if v})}\n\n"
                f"Missing slots: {', '.join(target_missing)}\n\n"
                f"Conversation:\n{format_history(state.history)}"
            ),
        ]
        result = self._generator.run(messages=messages)
        payload = extract_json_object(reply_text(result["replies"]))
        ask = AskResult.model_validate(payload)
        if ask.target_slot not in CORE_SLOTS and ask.target_slot != "context":
            ask = AskResult(target_slot=target_missing[0], question=ask.question)
        return ask.question


def create_gathering_brain(generator: GoogleGenAIChatGenerator) -> GatheringBrain:
    return GatheringBrain(generator=generator)


__all__ = [
    "ASK_PROMPT",
    "EXTRACT_PROMPT",
    "PROMPT",
    "AskResult",
    "GatheringBrain",
    "SlotExtraction",
    "create_gathering_brain",
]
