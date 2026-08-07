"""Run canned conversations through Visit-Prep."""

from __future__ import annotations

import logging
import sys
from contextlib import nullcontext

from dotenv import load_dotenv
from haystack import Pipeline

from visit_prep.pipeline import build_coordinator_pipeline, run_turn
from visit_prep.state import Phase, VisitPrepState

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("visit_prep.examples.run_scenarios")

SCENARIOS: dict[str, list[str]] = {
    "greeting": ["Hello!"],
    "meta": ["What can you help me with?"],
    "out_of_scope": ["What medication should I take for this headache?"],
    "emergency": ["I'm having crushing chest pain and can't breathe."],
    "health_gathering": [
        "I've had a dull headache for a few days.",
        "It started gradually about three days ago.",
        "It's mostly on both temples.",
        "It feels like a constant pressure.",
        "Maybe a 4 out of 10.",
        "It comes and goes through the day.",
        "Bright screens make it worse.",
        "Rest and water help a little.",
        "Just some mild neck stiffness.",
    ],
    "red_flag_mid_gathering": [
        "I've been feeling unwell.",
        "It started yesterday with mild nausea.",
        "Now I'm having the worst headache of my life and slurred speech.",
    ],
}


def run_scenario(
    name: str,
    messages: list[str],
    *,
    pipeline: Pipeline,
    turn_hook=None,
) -> VisitPrepState:
    """Run one scenario. ``turn_hook`` optionally wraps each turn (see run_scenarios_traced)."""
    state = VisitPrepState()
    logger.info("=== Scenario: %s ===", name)

    for message in messages:
        with turn_hook(message) if turn_hook else nullcontext(None) as turn:
            result = run_turn(message, state, pipeline=pipeline)
            if turn is not None:
                turn.output = result["response"]
        state = result["state"]
        logger.info("User: %s", message)
        logger.info("Assistant: %s", result["response"][:200])
        logger.info("Phase: %s", state.phase.value)

    return state


def main() -> int:
    load_dotenv()

    # Build the pipeline once and reuse it across scenarios: the generator and the
    # four Agents only need constructing once.
    try:
        pipeline = build_coordinator_pipeline()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    for name, messages in SCENARIOS.items():
        final_state = run_scenario(name, messages, pipeline=pipeline)
        if name == "emergency" and final_state.phase != Phase.ESCALATED:
            logger.error("Expected ESCALATED for emergency scenario")
            return 1
        if name == "red_flag_mid_gathering" and final_state.phase != Phase.ESCALATED:
            logger.error("Expected ESCALATED for mid-gathering red flag")
            return 1

    logger.info("All scenarios completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
