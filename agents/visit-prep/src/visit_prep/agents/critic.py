"""Safety-critic specialist Agent."""

from __future__ import annotations

from haystack.components.agents import Agent
from haystack.components.generators.chat.types import ChatGenerator

from visit_prep.tools import build_submit_verdict_tool

CRITIC_SYSTEM_PROMPT = """\
You review a visit-prep summary before it reaches the user. Reject if the summary names a \
likely diagnosis, ranks possibilities, suggests treatment or medication, includes any fact \
not present in the provided slots, or formats an apparent emergency as routine visit-prep.

Always call submit_verdict with your decision. If you reject, give specific, actionable \
feedback for a single rewrite.
"""

# `submit_verdict` writes the decision here, so callers read a bool instead of parsing text.
CRITIC_STATE_SCHEMA = {
    "approved": {"type": bool},
    "feedback": {"type": str},
}


def create_critic_agent(generator: ChatGenerator) -> Agent:
    """Build the adversarial reviewer with veto power over the summary."""
    return Agent(
        chat_generator=generator,
        tools=[build_submit_verdict_tool()],
        system_prompt=CRITIC_SYSTEM_PROMPT,
        state_schema=CRITIC_STATE_SCHEMA,
        exit_conditions=["submit_verdict"],
        max_agent_steps=3,
    )


__all__ = ["CRITIC_STATE_SCHEMA", "CRITIC_SYSTEM_PROMPT", "create_critic_agent"]
