"""Run canned scenarios with Rhesis Haystack tracing enabled."""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# tracing.py must load before any Haystack import (pipeline, run_scenarios).
from dr_rhesis.tracing import (  # noqa: E402
    enable_rhesis_tracing,
    flush_rhesis_tracing,
    set_trace_session,
)
from dr_rhesis.pipeline import build_intent_pipeline, build_turn_components  # noqa: E402
from dr_rhesis.state import Phase  # noqa: E402

_EXAMPLES_DIR = Path(__file__).resolve().parent
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from run_scenarios import SCENARIOS, run_scenario  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("dr_rhesis.examples.run_scenarios_traced")


def main() -> int:
    if not enable_rhesis_tracing():
        logger.error(
            "Rhesis tracing is not configured. Set RHESIS_API_KEY and "
            "RHESIS_PROJECT_ID in .env (see .env.example)."
        )
        return 1

    try:
        components = build_turn_components()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    pipeline = build_intent_pipeline(components)

    try:
        for name, messages in SCENARIOS.items():
            set_trace_session(str(uuid.uuid4()))
            final_state = run_scenario(name, messages, pipeline=pipeline, components=components)
            if name == "emergency" and final_state.phase != Phase.ESCALATED:
                logger.error("Expected ESCALATED for emergency scenario")
                return 1
            if name == "red_flag_mid_gathering" and final_state.phase != Phase.ESCALATED:
                logger.error("Expected ESCALATED for mid-gathering red flag")
                return 1
        logger.info("All traced scenarios completed.")
        return 0
    finally:
        flush_rhesis_tracing()


if __name__ == "__main__":
    sys.exit(main())
