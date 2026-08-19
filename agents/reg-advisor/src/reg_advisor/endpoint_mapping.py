"""Rhesis endpoint name and field mappings for the Reg-Advisor chat turn.

Shared by the FastAPI ``/chat`` route (``app.py``) and the playground connector
(``examples/serve_playground.py``) so the two cannot drift apart: both register
the *same* logical endpoint with the Rhesis backend, and a mapping that differed
between them would silently produce two incompatible shapes for one endpoint
name.

The mappings are Jinja templates the ``@endpoint`` decorator evaluates -- request
templates against the call's keyword arguments, response templates against the
returned object.
"""

from __future__ import annotations

from typing import Final

ENDPOINT_NAME: Final[str] = "reg_advisor_chat"

ENDPOINT_DESCRIPTION: Final[str] = (
    "Chat with the Reg-Advisor Google ADK multi-agent system, which works out which "
    "EU and US health-product regulatory regime a product falls into. Not legal advice."
)

# ``input`` and ``session_id`` are the standard request fields Rhesis sends.
REQUEST_MAPPING: Final[dict[str, str]] = {
    "message": "{{ input }}",
    "conversation_id": "{{ session_id | default(none) }}",
}

# Evaluated against the ChatResponse the traced entry point returns. ``phase`` is
# an enum, so it is stringified before ``tojson`` sees it.
RESPONSE_MAPPING: Final[dict[str, str]] = {
    "output": "{{ response }}",
    "session_id": "{{ conversation_id }}",
    "metadata": "{{ {'phase': phase | string, 'turn': turn} | tojson }}",
}

__all__ = [
    "ENDPOINT_DESCRIPTION",
    "ENDPOINT_NAME",
    "REQUEST_MAPPING",
    "RESPONSE_MAPPING",
]
