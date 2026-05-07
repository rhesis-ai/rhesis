"""Generate Microsoft Agent Framework traces with the Polymath workflow.

This script's only job is to fire a handful of representative queries through
the Polymath multi-agent workflow so the Rhesis SDK's MAF integration has
something real to translate and ship to the backend.

Run:

    cd agents/polymath
    uv run python examples/run_traces.py

Required env vars:

    GOOGLE_API_KEY      - Gemini key (also accepts GEMINI_API_KEY)

Optional env vars:

    POLYMATH_MODEL      - Gemini model id (default: gemini-2.0-flash)
    RHESIS_API_KEY      - Set both to ship spans to the Rhesis backend
    RHESIS_PROJECT_ID

Each query produces a small but rich trace tree:

    function.workflow.run
    +-- function.workflow.executor.process (per executor activation)
        +-- ai.agent.invoke (per agent activation)
            +-- ai.llm.invoke (per chat completion)
            +-- ai.tool.invoke (per tool call, with input/output events)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from polymath.workflow import build_workflow, invoke_polymath_async
from rhesis.sdk import RhesisClient
from rhesis.sdk.clients import DisabledClient
from rhesis.sdk.telemetry import auto_instrument

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("polymath.examples.run_traces")

# A trio of queries that, between them, exercise every span shape the SDK's
# MAF translator covers (chat, agent invoke, tool invoke, workflow spans).
QUERIES: list[tuple[str, str]] = [
    (
        "Pure math",
        "Compute (3 + 5) * 2^4 and then take the square root of the result.",
    ),
    (
        "Pure info",
        "What time is it in Tokyo right now? Then give me a one-sentence "
        "summary of Tokyo from Wikipedia.",
    ),
    (
        "Mixed",
        "What is 17 squared, and what's the current minute value in Berlin "
        "(Europe/Berlin) right now?",
    ),
]


def _section(title: str) -> None:
    bar = "=" * 80
    logger.info(bar)
    logger.info(title)
    logger.info(bar)


async def _run_one(workflow, label: str, query: str) -> None:
    _section(f"[{label}] {query}")
    result = await invoke_polymath_async(workflow, query)
    logger.info("Agents: %s", result["agent_workflow"])
    logger.info("Tools : %s", result["tool_chain"])
    logger.info("--- Final answer ---")
    logger.info(result["response"])


async def main() -> None:
    load_dotenv()

    # Initialise Rhesis client and turn on the MAF integration. We gate
    # construction on the credentials themselves: ``RhesisClient.__init__``
    # eagerly installs OTEL providers + the Rhesis OTLP exporter, so building
    # one without an API key / project id would attempt outbound exports
    # against ``project_id="unknown"`` with ``Authorization: Bearer None``.
    # The constructor side-effect (registering as the default client for
    # ``@endpoint`` / ``@observe``) is all we need here, so we discard the
    # returned instance.
    if os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"):
        RhesisClient.from_environment()
    else:
        logger.info(
            "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; using DisabledClient (no remote traces)."
        )
        DisabledClient()

    instrumented = auto_instrument("agent_framework")
    logger.info("auto_instrument: %s", instrumented)

    workflow = build_workflow()

    for label, query in QUERIES:
        try:
            await _run_one(workflow, label, query)
        except Exception:  # noqa: BLE001
            logger.exception("Query failed (this still produces an error span):")

    _section("Done")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
