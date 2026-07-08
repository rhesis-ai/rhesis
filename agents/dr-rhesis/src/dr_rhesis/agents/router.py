"""Intent classification subagent."""

from __future__ import annotations

from typing import Literal

from haystack import component
from haystack.dataclasses import ChatMessage
from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator
from pydantic import BaseModel, ValidationError

from dr_rhesis.state import DrRhesisState
from dr_rhesis.utils import extract_json_object, format_history, reply_text

IntentLabel = Literal["greeting", "meta", "out_of_scope", "emergency", "health_concern"]

PROMPT = """You classify a single user message in a visit-preparation health assistant. Output \
ONLY JSON: {"intent": "<label>"} where label is one of: greeting, meta, out_of_scope, \
emergency, health_concern. Use emergency when the message describes potentially \
life-threatening symptoms. Use out_of_scope when the user asks for a diagnosis, medication, \
or treatment. Use health_concern when the user describes a symptom to prepare a visit around. \
Use meta for questions about what you do. Do not explain. Output JSON only."""


class IntentResult(BaseModel):
    intent: IntentLabel


@component
class IntentRouter:
    """Classify the incoming user message into exactly one intent label."""

    def __init__(self, generator: GoogleGenAIChatGenerator) -> None:
        self._generator = generator

    @component.output_types(intent=str, raw_json=dict)
    def run(self, message: str, state: DrRhesisState) -> dict[str, object]:
        messages = [
            ChatMessage.from_system(PROMPT),
            ChatMessage.from_user(
                f"Recent conversation:\n{format_history(state.history)}\n\n"
                f"Latest user message:\n{message}"
            ),
        ]
        result = self._generator.run(messages=messages)
        text = reply_text(result["replies"])
        payload = extract_json_object(text)
        try:
            parsed = IntentResult.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"Invalid intent JSON from router: {payload}") from exc
        return {"intent": parsed.intent, "raw_json": payload}


def create_intent_router(generator: GoogleGenAIChatGenerator) -> IntentRouter:
    return IntentRouter(generator=generator)


__all__ = [
    "PROMPT",
    "IntentLabel",
    "IntentResult",
    "IntentRouter",
    "create_intent_router",
]
