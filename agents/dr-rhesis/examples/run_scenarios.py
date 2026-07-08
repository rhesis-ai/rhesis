"""Run canned per-intent conversations through Dr-Rhesis."""

from __future__ import annotations

import logging
import sys
import uuid

from dotenv import load_dotenv

from dr_rhesis.pipeline import TurnComponents, build_intent_pipeline, run_turn
from dr_rhesis.state import Phase, DrRhesisState

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("dr_rhesis.examples.run_scenarios")

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
    components: TurnComponents | None = None,
) -> DrRhesisState:
    pipeline = build_intent_pipeline(components)
    state = DrRhesisState()
    conv_id = str(uuid.uuid4())
    logger.info("=== Scenario: %s (%s) ===", name, conv_id)

    for message in messages:
        result = run_turn(message, state, pipeline=pipeline, components=components)
        state = result["state"]
        logger.info("User: %s", message)
        logger.info("Intent: %s", result.get("intent"))
        logger.info("Assistant: %s", result["response"][:200])
        logger.info("Phase: %s", state.phase.value)

    return state


def main() -> int:
    load_dotenv()

    try:
        from dr_rhesis.pipeline import build_turn_components

        components = build_turn_components()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    for name, messages in SCENARIOS.items():
        final_state = run_scenario(name, messages, components=components)
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
