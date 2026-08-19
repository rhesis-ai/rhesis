"""Keep a persistent Rhesis connector open so the playground can chat live.

Unlike ``examples/run_scenarios_traced.py`` (a one-shot batch that runs the
scripted conversations and exits), this script opens a *long-lived* WebSocket to
the Rhesis backend and registers Reg-Advisor as an ``@endpoint``. The Rhesis
playground can then send queries to it continuously: each turn runs the ADK
coordinator locally, remembers prior turns per ``conversation_id``, and ships
traces back to Rhesis.

The process blocks until you press Ctrl+C, so the playground always has a live
endpoint to talk to.

Requires Rhesis credentials (the connector cannot register without them):

    RHESIS_API_KEY=...
    RHESIS_PROJECT_ID=...

Run from ``agents/reg-advisor/``:

    uv run python examples/serve_playground.py
"""

from __future__ import annotations

import logging
import os
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\] feature .*", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rhesis.sdk import RhesisClient, endpoint  # noqa: E402
from rhesis.sdk.telemetry import auto_instrument  # noqa: E402

from reg_advisor.endpoint_mapping import (  # noqa: E402
    ENDPOINT_DESCRIPTION,
    ENDPOINT_NAME,
    REQUEST_MAPPING,
    RESPONSE_MAPPING,
)
from reg_advisor.knowledge import validate_knowledge_base  # noqa: E402
from reg_advisor.session import run_chat_turn  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("reg_advisor.examples.serve_playground")


def _build_chat_endpoint():
    """Register the Reg-Advisor turn as a Rhesis ``@endpoint`` and return it.

    Uses the same mappings as the FastAPI ``/chat`` route (imported from
    ``endpoint_mapping``), so the playground talks to this connector the same way.
    """

    @endpoint(
        name=ENDPOINT_NAME,
        description=ENDPOINT_DESCRIPTION,
        request_mapping=REQUEST_MAPPING,
        response_mapping=RESPONSE_MAPPING,
    )
    def reg_advisor_chat(message: str, conversation_id: str | None = None) -> dict:
        logger.info("=" * 80)
        logger.info("PLAYGROUND TURN | conversation_id=%s", conversation_id)
        logger.info("Q: %s", message[:100])
        logger.info("=" * 80)

        # The connector runs this sync handler in a thread pool, and
        # ``run_chat_turn`` opens a fresh event loop per turn. reg-advisor already
        # builds a new ADK Runner per turn, so nothing is shared across loops.
        result = run_chat_turn(message, conversation_id=conversation_id)
        state = result["state"]

        logger.info("--- Reply ---")
        logger.info(result["response"])
        logger.info("Phase: %s | turn: %s", state.phase, state.turn)

        return {
            "response": result["response"],
            "conversation_id": result["conversation_id"],
            "phase": state.phase,
            "turn": state.turn,
        }

    return reg_advisor_chat


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    if not (os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID")):
        logger.error(
            "RHESIS_API_KEY and RHESIS_PROJECT_ID are required to serve the playground "
            "connector. Set them in your .env and try again. (For a one-shot traced run "
            "without the playground, use run_scenarios_traced.py.)"
        )
        sys.exit(1)

    validate_knowledge_base()

    client = RhesisClient.from_environment()
    instrumented = auto_instrument("google_adk")
    logger.info("auto_instrument: %s", instrumented)

    _build_chat_endpoint()
    logger.info(
        "Reg-Advisor coordinator registered as '%s'. Opening persistent connector so the "
        "playground can send queries live...",
        ENDPOINT_NAME,
    )

    # Blocks on the WebSocket until interrupted (Ctrl+C).
    client.connect()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
