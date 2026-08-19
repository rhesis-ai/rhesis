"""The same scenarios as ``run_scenarios.py``, with Rhesis tracing switched on.

The only difference between the two files is the block below: turn on the SDK's MAF
integration, then run the identical scenarios. Nothing is duplicated, so the behavioural
check and the trace-generating run can never drift apart.

Each scenario is one conversation with a stable id, so its turns group into a multi-turn
conversation in Rhesis rather than a pile of unrelated traces. A planning turn produces
the full span tree - endpoint, workflow, per-agent activations, handoff edges, LLM calls
and tool calls.

Run from ``agents/travel-agent/``:

    uv run python examples/run_scenarios_traced.py

Required:
    GOOGLE_API_KEY                    - Gemini key (also accepts GEMINI_API_KEY)
    RHESIS_API_KEY, RHESIS_PROJECT_ID - to actually ship spans
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from rhesis.sdk import RhesisClient
from rhesis.sdk.clients import DisabledClient
from rhesis.sdk.telemetry import auto_instrument, shutdown_tracer_provider

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("travel_agent.examples.traced")


def _enable_tracing() -> None:
    """Turn on the SDK's MAF integration - the line this whole demo exists to exercise."""
    if os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"):
        RhesisClient.from_environment()
    else:
        logger.warning(
            "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; spans will be produced but not shipped."
        )
        DisabledClient()
    auto_instrument("agent_framework")


async def main() -> int:
    load_dotenv()
    _enable_tracing()

    # Imported after instrumentation so every agent activation is traced.
    from examples.run_scenarios import main as run_all

    try:
        return await run_all()
    finally:
        # Short-lived process: flush the last batch before it exits.
        shutdown_tracer_provider()


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raise SystemExit(asyncio.run(main()))
