"""History-gathering specialist Agent."""

from __future__ import annotations

from haystack.components.agents import Agent
from haystack.components.generators.chat.types import ChatGenerator

from visit_prep.tools import build_record_slots_tool

# `slot_status` is rendered into the system prompt by the caller: Agent State is invisible to
# the model, so without it the specialist cannot tell what it already knows or already asked.
HISTORY_SYSTEM_PROMPT = """\
You help a user prepare for a doctor's visit by collecting a structured symptom history \
(OPQRST / SOCRATES). You never diagnose and never suggest treatment.

What is already on file:
{{ slot_status }}

On each turn:
1. Call record_slots with any newly stated fields from the latest user message. A short answer \
usually answers the question you asked just before it — read the conversation to see which slot \
it belongs to.
2. If core slots are still missing, ask ONE natural question about the single most useful \
missing slot. Ask only one thing, and never re-ask something already on file.
3. If nothing is missing, briefly confirm you have everything you need.

Do not invent facts. Keep questions short and conversational.
"""

HISTORY_STATE_SCHEMA = {
    "slots": {"type": dict},
    "chief_complaint": {"type": str},
}


def create_history_agent(generator: ChatGenerator) -> Agent:
    """Build the history specialist that extracts slots and asks one follow-up."""
    return Agent(
        chat_generator=generator,
        tools=[build_record_slots_tool()],
        system_prompt=HISTORY_SYSTEM_PROMPT,
        state_schema=HISTORY_STATE_SCHEMA,
        exit_conditions=["text"],
        max_agent_steps=6,
    )


__all__ = ["HISTORY_STATE_SCHEMA", "HISTORY_SYSTEM_PROMPT", "create_history_agent"]
