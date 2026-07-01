"""Generate Microsoft Agent Framework traces with the vanilla travel agent.

This script's only job is to fire a handful of representative queries through
the Travel Agent multi-agent handoff workflow so the Rhesis SDK's MAF
integration has something real to translate and ship to the backend. It is a
minimal in-process ``auto_instrument`` smoke test: turn Rhesis on, run the
workflow, and let the SDK produce and ship every span automatically. There is
no manual span creation and no manual attribute stamping; the only manual step
is a single ``shutdown_tracer_provider()`` at the end to flush the last batch
before this short-lived process exits.

Run from ``agents/travel-agent/``:

    uv run python examples/run_traces.py

Required env vars:

    GOOGLE_API_KEY      - Gemini key (also accepts GEMINI_API_KEY)

Optional env vars:

    TRAVEL_AGENT_MODEL  - Gemini model id (default: gemini-2.0-flash)
    RHESIS_API_KEY      - Set both to ship spans to the Rhesis backend
    RHESIS_PROJECT_ID

Each scenario is one workflow run and produces a single plain trace rooted at
MAF's ``function.workflow.run``. These are one-shot single-turn runs: they do
not set a conversation/session id, so the MAF integration leaves them as
ordinary traces (they appear in the default Traces view, not as multi-turn
conversations). Multi-turn grouping is exercised separately by the chat session
path (``travel_agent.session.run_chat_turn``), used by the playground/app:

    function.workflow.run                     (trace root)
    +-- function.workflow.executor.process    (per executor activation)
        +-- ai.agent.invoke                   (per agent activation)
            +-- ai.llm.invoke                 (per chat completion)
            +-- ai.tool.invoke                (per tool call, with input/output events)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid

from dotenv import load_dotenv

from rhesis.sdk import RhesisClient
from rhesis.sdk.clients import DisabledClient
from rhesis.sdk.telemetry import auto_instrument, shutdown_tracer_provider
from travel_agent.workflow import build_travel_workflow, invoke_travel_workflow_async

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("travel_agent.examples.run_traces")

# Three single-turn scenarios that, between them, exercise every routing path and span
# shape the SDK's MAF translator covers (coordinator, destination finder,
# sightseeing scout, logistics planner).
SCENARIOS: list[tuple[str, str]] = [
    (
        # No destination + "surprise" => destination_finder picks a city,
        # then sightseeing_scout and logistics_planner fill in the rest.
        "Surprise trip",
        "Plan a family-friendly day trip at a random destination.",
    ),
    (
        # Names the city but no sights => sightseeing_scout suggests stops,
        # logistics_planner estimates travel; destination_finder is skipped.
        "Named city, no sights",
        "Plan me a relaxed day trip to Paris with cafes and art.",
    ),
    (
        # Names the city and sights => sightseeing_scout is skipped, but
        # logistics_planner still runs.
        "Named city and sights",
        (
            "Plan a family-friendly day trip to Barcelona visiting Sagrada Familia, "
            "Park Guell, La Boqueria, and one extra food stop."
        ),
    ),
]


def _section(title: str) -> None:
    bar = "=" * 80
    logger.info(bar)
    logger.info(title)
    logger.info(bar)


async def _run_scenario(label: str, query: str) -> None:
    """Run one single-turn scenario; auto_instrument captures the full trace tree."""
    conversation_id = str(uuid.uuid4())
    _section(f"[{label}] {query}")

    # Build a fresh workflow per scenario. MAF agents use
    # ``require_per_service_call_history_persistence=True``, so reusing a cached
    # workflow leaks prior scenarios' internal history into later runs.
    workflow = build_travel_workflow()
    result = await invoke_travel_workflow_async(
        workflow,
        query,
        conversation_id=conversation_id,
    )

    logger.info("Agents: %s", result["agent_workflow"])
    logger.info("Tools : %s", result["tool_chain"])
    logger.info("--- Travel plan ---")
    logger.info(result["response"])


async def main() -> None:
    load_dotenv()

    # Initialise the Rhesis client and turn on the MAF integration. We gate
    # construction on the credentials themselves: ``RhesisClient.__init__``
    # eagerly installs OTEL providers + the Rhesis OTLP exporter, so building
    # one without an API key / project id would attempt outbound exports
    # against ``project_id="unknown"`` with ``Authorization: Bearer None``.
    # The constructor side-effect (registering as the default client for
    # ``@endpoint`` / ``@observe``) is all we need here, so we discard the
    # returned instance.
    if os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"):
        RhesisClient.from_environment()
        logger.info(
            "Remote traces enabled for project %s (%s). "
            "Select this project in the frontend Traces page to view them.",
            os.getenv("RHESIS_PROJECT_ID"),
            os.getenv("RHESIS_BASE_URL", "http://localhost:8080"),
        )
    else:
        logger.warning(
            "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; using DisabledClient. "
            "Traces will NOT be shipped to the backend."
        )
        DisabledClient()

    instrumented = auto_instrument("agent_framework")
    logger.info("auto_instrument: %s", instrumented)

    try:
        for label, query in SCENARIOS:
            try:
                await _run_scenario(label, query)
            except Exception:  # noqa: BLE001
                logger.exception("Scenario failed (this still produces an error span):")
    finally:
        # This is a short-lived script: flush and shut the tracer provider down
        # explicitly so the final batch of spans is exported before the process
        # exits (the BatchSpanProcessor only flushes every few seconds otherwise).
        shutdown_tracer_provider()

    _section("Done")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
