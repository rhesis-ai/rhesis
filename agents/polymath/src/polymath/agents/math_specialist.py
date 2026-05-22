"""Math Specialist agent for the Polymath system.

Owns the local Python arithmetic tools. After producing a numeric answer the
agent should hand back to the coordinator (the handoff tool is auto-injected
by :class:`agent_framework_orchestrations.HandoffBuilder`).
"""

from __future__ import annotations

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from polymath.tools import MATH_TOOLS

INSTRUCTIONS = """You are the math specialist.

You answer arithmetic and numeric questions using these tools:

- add(a, b): a + b
- multiply(a, b): a * b
- power(base, exponent): base ** exponent
- square_root(x): sqrt(x), x must be non-negative

How to behave:

1. Decompose the requested computation into single-tool steps and call each tool in turn.
   Always use the tools rather than computing in your head.
2. State the final numeric result clearly in one short sentence.
3. Then hand control back to the coordinator using the provided handoff tool. Do not
   keep talking after handing off.
"""

DESCRIPTION = "Performs arithmetic with add / multiply / power / square_root tools."


def create_agent(client: OpenAIChatClient) -> Agent:
    """Build the Math Specialist :class:`Agent` instance.

    See :func:`polymath.agents.coordinator.create_agent` for the rationale
    behind ``require_per_service_call_history_persistence=True``.
    """
    return Agent(
        client=client,
        instructions=INSTRUCTIONS,
        name="math_specialist",
        description=DESCRIPTION,
        tools=MATH_TOOLS,
        require_per_service_call_history_persistence=True,
    )
