"""Info Specialist agent for the Polymath system.

Owns the HTTP-backed information tools. After answering, the agent should
hand back to the coordinator (the handoff tool is auto-injected by
:class:`agent_framework_orchestrations.HandoffBuilder`).
"""

from __future__ import annotations

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from polymath.tools import INFO_TOOLS

INSTRUCTIONS = """You are the info specialist.

You answer factual / time questions using these tools:

- get_current_time(timezone): current time in any IANA timezone (e.g. 'UTC',
  'Europe/Berlin', 'Asia/Tokyo'). Default is 'UTC'.
- wikipedia_summary(topic): a short English Wikipedia summary for a topic.

How to behave:

1. Pick the right tool(s) for the question and call them. Do not invent answers
   when a tool would give you ground truth.
2. Distill the tool output into one or two short sentences for the coordinator.
3. Then hand control back to the coordinator using the provided handoff tool.
   Do not keep talking after handing off.
"""

DESCRIPTION = "Fetches current time and Wikipedia summaries via real HTTP calls."


def create_agent(client: OpenAIChatClient) -> Agent:
    """Build the Info Specialist :class:`Agent` instance.

    See :func:`polymath.agents.coordinator.create_agent` for the rationale
    behind ``require_per_service_call_history_persistence=True``.
    """
    return Agent(
        client=client,
        instructions=INSTRUCTIONS,
        name="info_specialist",
        description=DESCRIPTION,
        tools=INFO_TOOLS,
        require_per_service_call_history_persistence=True,
    )
