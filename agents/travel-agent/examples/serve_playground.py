"""Keep a persistent Rhesis connector open so the playground can chat live.

Unlike ``run_scenarios.py`` (a batch that replays fixed turns and exits), this opens a
long-lived WebSocket to the Rhesis backend and registers the travel agent as an
``@endpoint``. The playground can then send queries continuously: each turn runs locally,
remembers the trip brief per ``conversation_id``, and ships traces back to Rhesis.

The process blocks until you press Ctrl+C.

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

from dotenv import load_dotenv

from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.telemetry import auto_instrument
from travel_agent.endpoint_mapping import (
    ENDPOINT_DESCRIPTION,
    ENDPOINT_NAME,
    REQUEST_MAPPING,
    RESPONSE_MAPPING,
)
from travel_agent.router import COORDINATOR_NAME
from travel_agent.session import run_chat_turn_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("travel_agent.examples.serve_playground")


def _build_chat_endpoint():
    """Register the travel agent as a Rhesis ``@endpoint`` and return it.

    The mappings are imported rather than restated: this connector and the FastAPI route
    used to keep their own copies and had already drifted apart.
    """

    @endpoint(
        name=ENDPOINT_NAME,
        description=ENDPOINT_DESCRIPTION,
        request_mapping=REQUEST_MAPPING,
        response_mapping=RESPONSE_MAPPING,
    )
    def travel_agent_chat(message: str, conversation_id: str | None = None) -> dict:
        logger.info("Playground turn | conversation=%s | %.100s", conversation_id, message)

        # The connector runs this sync handler in a thread pool, and
        # ``run_chat_turn_sync`` opens a fresh event loop per turn. Nothing MAF-shaped is
        # cached across those loops - the workflow is built inside the turn.
        result = run_chat_turn_sync(message, conversation_id=conversation_id)

        logger.info("Reply: %.200s", result["response"])
        logger.info("Agents: %s | Tools: %s", result["agent_workflow"], result["tool_chain"])
        if result["degraded_services"]:
            logger.warning("Degraded services: %s", result["degraded_services"])

        return {
            "response": result["response"],
            "conversation_id": result["conversation_id"],
            "phase": result["phase"],
            "tools_called": result["tools_called"],
            "agents_involved": result["agents_involved"],
            "agent_workflow": result["agent_workflow"],
            "tool_chain": result["tool_chain"],
            "handoffs": result["handoffs"],
            "degraded_services": result["degraded_services"],
            "agent": COORDINATOR_NAME,
        }

    return travel_agent_chat


def main() -> None:
    load_dotenv()

    if not (os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID")):
        logger.error(
            "RHESIS_API_KEY and RHESIS_PROJECT_ID are required to serve the playground "
            "connector. Set them in your .env and try again. (For a run without the "
            "playground, use run_scenarios.py.)"
        )
        sys.exit(1)

    client = RhesisClient.from_environment()
    logger.info("auto_instrument: %s", auto_instrument("agent_framework"))

    _build_chat_endpoint()
    logger.info(
        "Travel agent registered as '%s'. Opening persistent connector so the playground "
        "can send queries live...",
        ENDPOINT_NAME,
    )

    # Blocks on the WebSocket until interrupted (Ctrl+C).
    client.connect()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
