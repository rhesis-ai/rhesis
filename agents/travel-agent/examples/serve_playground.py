"""Keep a persistent Rhesis connector open so the playground can chat live.

Unlike ``examples/run_traces.py`` (a one-shot batch that fires a few prompts and
exits), this script opens a *long-lived* WebSocket to the Rhesis backend and
registers the travel agent as an ``@endpoint``. The Rhesis playground can then
send queries to it continuously: each turn runs the workflow locally, remembers
prior turns per ``conversation_id``, and ships traces back to Rhesis.

The process blocks until you press Ctrl+C, so the playground always has a live
endpoint to talk to.

Requires Rhesis credentials (the connector cannot register without them):

    RHESIS_API_KEY=...
    RHESIS_PROJECT_ID=...

Run from ``agents/travel-agent/``:

    uv run python examples/serve_playground.py
"""

from __future__ import annotations

import logging
import os
import sys
import uuid

from agent_framework import Message
from dotenv import load_dotenv
from opentelemetry import trace as otel_trace
from rhesis.telemetry.constants import ConversationContext

from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.telemetry import auto_instrument
from travel_agent import build_travel_workflow, invoke_travel_workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("travel_agent.examples.serve_playground")

# Per-conversation message history so the playground gets real multi-turn
# memory. In-memory is fine for a demo; production would persist this.
conversations: dict[str, list[Message]] = {}


def _build_chat_endpoint():
    """Register the travel workflow as a Rhesis ``@endpoint`` and return it.

    The ``request_mapping`` / ``response_mapping`` mirror the FastAPI app's
    ``/chat`` route so the playground talks to this connector the same way.
    """

    @endpoint(
        name="travel_agent_chat",
        description="Chat with the Travel Agent MAF multi-agent system.",
        request_mapping={
            "message": "{{ input }}",
            "conversation_id": "{{ session_id | default(none) }}",
        },
        response_mapping={
            "output": "{{ response }}",
            "session_id": "{{ conversation_id }}",
            "tool_calls": "{{ tools_called | tojson }}",
            "agents_involved": "{{ agents_involved | tojson }}",
            "agent_workflow": "{{ agent_workflow }}",
            "tool_chain": "{{ tool_chain }}",
        },
    )
    def travel_agent_chat(message: str, conversation_id: str | None = None) -> dict:
        conv_id = conversation_id or str(uuid.uuid4())

        logger.info("=" * 80)
        logger.info("PLAYGROUND TURN | conversation_id=%s", conv_id)
        logger.info("Q: %s", message[:100])
        logger.info("=" * 80)

        # Stamp conversation attributes on the active @endpoint span (the turn
        # root). On the first turn the playground sends no conversation_id, so
        # the SDK cannot inject one before the span is created.
        conv_attr = ConversationContext.SpanAttributes
        max_io = ConversationContext.MAX_IO_LENGTH
        span = otel_trace.get_current_span()
        span.set_attribute(conv_attr.IS_TURN_ROOT, True)
        span.set_attribute(conv_attr.CONVERSATION_ID, conv_id)
        span.set_attribute(conv_attr.CONVERSATION_INPUT, message[:max_io])

        # Replay prior turns so the workflow actually remembers the conversation.
        history = conversations.get(conv_id, [])
        workflow = build_travel_workflow()
        result = invoke_travel_workflow(
            workflow,
            message,
            conversation_history=history,
            conversation_id=conv_id,
        )
        conversations[conv_id] = result["messages"]

        span.set_attribute(conv_attr.CONVERSATION_OUTPUT, (result["response"] or "")[:max_io])

        logger.info("--- Travel plan ---")
        logger.info(result["response"])
        logger.info("Agent workflow: %s", result["agent_workflow"])
        logger.info("Tool chain: %s", result["tool_chain"])

        return {
            "response": result["response"],
            "conversation_id": conv_id,
            "tools_called": result["tools_called"],
            "agents_involved": result["agents_involved"],
            "agent_workflow": result["agent_workflow"],
            "tool_chain": result["tool_chain"],
        }

    return travel_agent_chat


def main() -> None:
    load_dotenv()

    if not (os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID")):
        logger.error(
            "RHESIS_API_KEY and RHESIS_PROJECT_ID are required to serve the "
            "playground connector. Set them in your .env and try again. "
            "(For a one-shot run without the playground, use run_traces.py.)"
        )
        sys.exit(1)

    client = RhesisClient.from_environment()
    instrumented = auto_instrument("agent_framework")
    logger.info("auto_instrument: %s", instrumented)

    _build_chat_endpoint()
    logger.info(
        "Travel multi-agent workflow registered as 'travel_agent_chat'. Opening persistent "
        "connector so the playground can send queries live..."
    )

    # Blocks on the WebSocket until interrupted (Ctrl+C).
    client.connect()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
