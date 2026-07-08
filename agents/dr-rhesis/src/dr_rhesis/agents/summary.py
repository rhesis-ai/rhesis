"""Summary writer subagent."""

from __future__ import annotations

from haystack import component
from haystack.dataclasses import ChatMessage
from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator

from dr_rhesis.state import DrRhesisState
from dr_rhesis.utils import format_slots, reply_text

PROMPT = """Using ONLY the information in the provided slots, write a short visit-prep summary: \
a chronological timeline of the symptom, then a brief list of questions the user could ask \
their doctor. Do not add any symptom, cause, or possibility the user did not state. Do not \
diagnose or suggest treatment."""


@component
class SummaryWriter:
    """Turn filled slots into a visit-prep hand-off summary."""

    def __init__(self, generator: GoogleGenAIChatGenerator) -> None:
        self._generator = generator

    @component.output_types(summary=str)
    def run(
        self,
        state: DrRhesisState,
        fix: str = "",
    ) -> dict[str, str]:
        fix_block = f"\n\nRewrite guidance from safety reviewer:\n{fix}" if fix else ""
        messages = [
            ChatMessage.from_system(PROMPT + fix_block),
            ChatMessage.from_user(
                f"Chief complaint: {state.chief_complaint or '(not recorded)'}\n"
                f"Slots:\n{format_slots(state.slots.model_dump())}"
            ),
        ]
        result = self._generator.run(messages=messages)
        return {"summary": reply_text(result["replies"])}


def create_summary_writer(generator: GoogleGenAIChatGenerator) -> SummaryWriter:
    return SummaryWriter(generator=generator)


__all__ = ["PROMPT", "SummaryWriter", "create_summary_writer"]
