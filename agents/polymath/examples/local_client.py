"""Minimal Polymath client that pushes traces to a local Rhesis backend.

Wires `polymath.workflow.build_workflow()` into the Rhesis SDK's MAF
auto-instrumentation so a single query produces a full trace tree
(workflow / agent / llm / tool spans) in your local Rhesis app.

Run from `agents/polymath/`:

    uv run python examples/local_client.py
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from polymath.workflow import build_workflow, invoke_polymath_async
from rhesis.sdk import RhesisClient
from rhesis.sdk.clients import DisabledClient
from rhesis.sdk.telemetry import auto_instrument

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("polymath.examples.local_client")

QUERY = (
    "What is 17 squared, and what's the current minute value in Berlin (Europe/Berlin) right now?"
)


async def main() -> None:
    load_dotenv()

    # Gate construction on the credentials themselves: ``RhesisClient.__init__``
    # eagerly installs OTEL providers + the Rhesis OTLP exporter, so building
    # one without an API key / project id would attempt outbound exports
    # against ``project_id="unknown"`` with ``Authorization: Bearer None``.
    if os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"):
        client = RhesisClient.from_environment()
        logger.info(
            "RhesisClient initialised: project=%s base_url=%s",
            getattr(client, "project_id", None),
            getattr(client, "_base_url", None),
        )

    enabled = auto_instrument("agent_framework")
    logger.info("auto_instrument('agent_framework') -> %s", enabled)

    workflow = build_workflow()

    logger.info("=" * 80)
    logger.info("Q: %s", QUERY)
    logger.info("=" * 80)
    result = await invoke_polymath_async(workflow, QUERY)

    logger.info("Agents: %s", result["agent_workflow"])
    logger.info("Tools : %s", result["tool_chain"])
    logger.info("--- Final answer ---")
    logger.info(result["response"])


if __name__ == "__main__":
    asyncio.run(main())
