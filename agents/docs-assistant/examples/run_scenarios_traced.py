"""Run the scripted scenarios with Rhesis tracing on.

A thin wrapper over ``examples/run_scenarios.py``: the same conversations and checks, but every
turn is shipped to Rhesis as a trace. Without Rhesis credentials the scenarios still run,
untraced. Run from the project root:

    uv run python examples/run_scenarios_traced.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "examples"))

logger = logging.getLogger("docs_assistant.examples.run_scenarios_traced")


def _enable_tracing() -> bool:
    """Install the Rhesis client and route Agents SDK spans to it.

    Gated on the credentials: ``RhesisClient`` installs OTel providers and starts shipping
    spans as soon as it is built, so without a key it would export to nowhere.
    """
    from rhesis.sdk import RhesisClient

    from docs_assistant import tracing

    if not tracing.rhesis_configured():
        logger.warning(
            "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; scenarios run, but no traces are shipped."
        )
        return False
    RhesisClient.from_environment()
    return tracing.install()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Tracing: %s", "on" if _enable_tracing() else "off")

    from run_scenarios import main as run_scenarios_main

    try:
        return run_scenarios_main()
    finally:
        # Short-lived process: flush the last batch before exiting, or it never leaves.
        from rhesis.telemetry.provider import shutdown_tracer_provider

        shutdown_tracer_provider()


if __name__ == "__main__":
    sys.exit(main())
