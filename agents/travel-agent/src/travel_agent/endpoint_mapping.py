"""The Rhesis ``@endpoint`` request/response mapping, defined once.

The FastAPI route and the playground connector both register the same endpoint. They used
to carry their own copies of this mapping and had already drifted apart, so it lives here
now and both import it.
"""

from __future__ import annotations

from typing import Final

ENDPOINT_NAME: Final[str] = "travel_agent_chat"
ENDPOINT_DESCRIPTION: Final[str] = "Chat with the Travel Agent MAF multi-agent system."

REQUEST_MAPPING: Final[dict[str, str]] = {
    "message": "{{ input }}",
    "conversation_id": "{{ session_id | default(none) }}",
}

RESPONSE_MAPPING: Final[dict[str, str]] = {
    "output": "{{ response }}",
    "session_id": "{{ conversation_id }}",
    "tool_calls": "{{ tools_called | tojson }}",
    "agents_involved": "{{ agents_involved | tojson }}",
    "agent_workflow": "{{ agent_workflow }}",
    "tool_chain": "{{ tool_chain }}",
    "metadata": (
        "{{ {'agent': agent, 'phase': phase, 'handoffs': handoffs, "
        "'degraded_services': degraded_services, 'tools_called': tools_called, "
        "'tool_chain': tool_chain, 'agents_involved': agents_involved, "
        "'agent_workflow': agent_workflow} | tojson }}"
    ),
}

__all__ = [
    "ENDPOINT_DESCRIPTION",
    "ENDPOINT_NAME",
    "REQUEST_MAPPING",
    "RESPONSE_MAPPING",
]
