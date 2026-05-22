"""Coordinator agent for the Polymath system.

The coordinator decides which specialist should handle the user's request and
synthesises the final answer once specialists hand back. ``HandoffBuilder``
auto-injects the actual handoff tools, so this agent doesn't declare any
domain tools of its own.
"""

from __future__ import annotations

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

INSTRUCTIONS = """You are the Polymath coordinator.

You manage two specialists:

- math_specialist: arithmetic and numeric computation (addition, multiplication,
  powers, square roots)
- info_specialist: live information from the internet (current time in any IANA
  timezone, short Wikipedia summaries)

How to behave:

1. Read the user's request and break it into the smallest set of sub-tasks needed to answer it.
2. For each sub-task, hand off to the appropriate specialist using the provided handoff tools.
   - For any arithmetic / numeric work, hand off to math_specialist.
   - For current time, dates, or factual lookups, hand off to info_specialist.
3. When a specialist returns control, decide whether more work is needed. If so, hand off again.
4. Once you have all the information needed, write a single concise final answer for the user
   that combines the specialist results. Do not list the agents or tools you used.

Always act — do not describe what you are about to do. If a request can be answered without
either specialist, answer it directly."""

DESCRIPTION = "Routes math and info questions to the right specialist and synthesises the answer."


def create_agent(client: OpenAIChatClient) -> Agent:
    """Build the coordinator :class:`Agent` instance.

    ``require_per_service_call_history_persistence=True`` is required by
    :class:`agent_framework_orchestrations.HandoffBuilder` (handoff workflows
    short-circuit tool calls via middleware, so per-service-call persistence
    is needed to keep local history consistent with the LLM service).
    """
    return Agent(
        client=client,
        instructions=INSTRUCTIONS,
        name="coordinator",
        description=DESCRIPTION,
        require_per_service_call_history_persistence=True,
    )
