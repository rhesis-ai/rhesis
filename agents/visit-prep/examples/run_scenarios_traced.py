"""Run canned scenarios with Rhesis Haystack tracing enabled."""

from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Must precede any Haystack import so span input/output content is captured.
os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "true")

from haystack_integrations.tracing.rhesis import RhesisTracing  # noqa: E402

from visit_prep.pipeline import build_coordinator_pipeline  # noqa: E402
from visit_prep.state import Phase  # noqa: E402

_EXAMPLES_DIR = Path(__file__).resolve().parent
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from run_scenarios import SCENARIOS, run_scenario  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("visit_prep.examples.run_scenarios_traced")


def main() -> int:
    tracing = RhesisTracing("Visit-Prep", turn_span_name="function.visit_prep_turn")
    if not tracing.enabled:
        logger.error(
            "Rhesis tracing is not configured. Set RHESIS_API_KEY in .env (see .env.example)."
        )
        return 1

    try:
        pipeline = build_coordinator_pipeline()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    try:
        for name, messages in SCENARIOS.items():
            # One conversation per scenario, so each lands in its own trace.
            tracing.start_conversation(str(uuid.uuid4()))
            final_state = run_scenario(name, messages, pipeline=pipeline, turn_hook=tracing.turn)
            if name == "emergency" and final_state.phase != Phase.ESCALATED:
                logger.error("Expected ESCALATED for emergency scenario")
                return 1
            if name == "red_flag_mid_gathering" and final_state.phase != Phase.ESCALATED:
                logger.error("Expected ESCALATED for mid-gathering red flag")
                return 1
        logger.info("All traced scenarios completed.")
        return 0
    finally:
        tracing.flush()


if __name__ == "__main__":
    sys.exit(main())
