"""Generate Microsoft Agent Framework traces with the vanilla travel agent.

This script's only job is to fire a handful of representative queries through
the Travel Agent multi-agent handoff workflow so the Rhesis SDK's MAF
integration has something real to translate and ship to the backend.

Each scenario is a single user turn. The script creates one Rhesis-visible
turn-root span per scenario so the frontend can render the Conversation tab
from ``rhesis.conversation.input`` / ``rhesis.conversation.output``.

Run from ``agents/travel-agent/``:

    uv run python examples/run_traces.py

Required env vars:

    GOOGLE_API_KEY      - Gemini key (also accepts GEMINI_API_KEY)

Optional env vars:

    TRAVEL_AGENT_MODEL  - Gemini model id (default: gemini-2.0-flash)
    RHESIS_API_KEY      - Set both to ship spans to the Rhesis backend
    RHESIS_PROJECT_ID

Each query produces a small but rich trace tree:

    function.travel_agent.run
    +-- function.workflow.build
    +-- function.workflow.run
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
import uuid

from dotenv import load_dotenv
from opentelemetry import trace

from rhesis.sdk import RhesisClient
from rhesis.sdk.clients import DisabledClient
from rhesis.sdk.telemetry import auto_instrument, shutdown_tracer_provider
from rhesis.telemetry.constants import ConversationContext
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
    """Run one single-turn scenario under a frontend-readable root span."""
    conversation_id = str(uuid.uuid4())
    attrs = ConversationContext.SpanAttributes

    _section(f"[{label}] {query}")

    # MAF's workflow/agent spans do not carry Rhesis conversation attributes.
    # This explicit turn-root span makes the frontend Conversation tab work and
    # keeps workflow.build/workflow.run under one trace tree for the scenario.
    tracer = trace.get_tracer("travel_agent.examples.run_traces")
    with tracer.start_as_current_span("function.travel_agent.run") as span:
        span.set_attribute(attrs.IS_TURN_ROOT, True)
        span.set_attribute(attrs.CONVERSATION_ID, conversation_id)
        span.set_attribute(
            attrs.CONVERSATION_INPUT,
            query[: ConversationContext.MAX_IO_LENGTH],
        )

        span.set_attribute("travel_agent.scenario", label)

        workflow = build_travel_workflow()
        result = await invoke_travel_workflow_async(
            workflow,
            query,
            conversation_id=conversation_id,
        )

        response = str(result["response"])
        span.set_attribute(
            attrs.CONVERSATION_OUTPUT,
            response[: ConversationContext.MAX_IO_LENGTH],
        )
        span.set_attribute("travel_agent.agent_workflow", result["agent_workflow"])
        span.set_attribute("travel_agent.tool_chain", result["tool_chain"])

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
    else:
        logger.info(
            "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; using DisabledClient (no remote traces)."
        )
        DisabledClient()

    instrumented = auto_instrument("agent_framework")
    logger.info("auto_instrument: %s", instrumented)

    for label, query in SCENARIOS:
        try:
            await _run_scenario(label, query)
        except Exception:  # noqa: BLE001
            logger.exception("Scenario failed (this still produces an error span):")

    _section("Done")
    shutdown_tracer_provider()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
