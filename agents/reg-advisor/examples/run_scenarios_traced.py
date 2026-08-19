"""Run the scripted scenarios with Rhesis tracing switched on.

A thin wrapper over ``examples/run_scenarios.py``: same conversations, same
post-conditions, but every agent activation, model call and tool call is shipped
to the Rhesis backend as a trace.

Needs a Gemini API key plus ``RHESIS_API_KEY`` and ``RHESIS_PROJECT_ID``. Without
the Rhesis credentials the scenarios still run, untraced. Run from the project
root:

    uv run python examples/run_scenarios_traced.py
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
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "examples"))

logger = logging.getLogger("reg_advisor.examples.run_scenarios_traced")


def _enable_tracing() -> bool:
    """Install the Rhesis client and turn on the Google ADK integration.

    Gated on the credentials themselves: ``RhesisClient.__init__`` eagerly
    installs OTEL providers and tries to ship spans, so constructing it without
    an API key / project id would export against ``project_id="unknown"`` with
    ``Authorization: Bearer None``.
    """
    from rhesis.sdk import RhesisClient
    from rhesis.sdk.clients import DisabledClient
    from rhesis.sdk.telemetry import auto_instrument

    if os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"):
        RhesisClient.from_environment()
    else:
        logger.warning(
            "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; using DisabledClient. "
            "Scenarios will run but traces will NOT be shipped."
        )
        DisabledClient()

    enabled = auto_instrument("google_adk")
    logger.info("Instrumented: %s", enabled or "nothing")
    return "google_adk" in enabled


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _enable_tracing()

    # Imported only after instrumentation is on, so every agent activation the
    # scenarios trigger is traced.
    from run_scenarios import main as run_scenarios_main

    try:
        return run_scenarios_main()
    finally:
        # Short-lived process: flush the last batch before it exits, or the final
        # scenario's spans never leave.
        from rhesis.telemetry.provider import shutdown_tracer_provider

        shutdown_tracer_provider()


if __name__ == "__main__":
    sys.exit(main())
