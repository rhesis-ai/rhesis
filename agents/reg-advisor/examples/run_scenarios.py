"""Scripted conversations covering every route Reg-Advisor can take.

Needs a Gemini API key: these run against the real model. Run from the project root:

    uv run python examples/run_scenarios.py

Acts as a smoke test, not just a demo — it checks a post-condition per scenario and exits
non-zero when one fails.
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

# ADK's experimental-feature notice is aimed at developers and only clutters the transcript.
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\] feature .*", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from reg_advisor.knowledge import validate_knowledge_base  # noqa: E402
from reg_advisor.session import StateStore, run_chat_turn  # noqa: E402
from reg_advisor.state import Phase, RegAdvisorState  # noqa: E402

logger = logging.getLogger("reg_advisor.examples.run_scenarios")

SCENARIOS: dict[str, list[str]] = {
    "greeting": ["Hello — what do you do?"],
    "out_of_scope": ["What is the capital of France?"],
    "referral": ["How do I word the claim so it isn't a device?"],
    # The brief's first example question, answered end to end. Each reply is deliberately
    # information-dense: the intake agent picks its own next question, so a scripted answer to
    # an assumed question order would not line up.
    "ppg_smartwatch": [
        "I'm building a mobile app that estimates atrial fibrillation risk from a smartwatch "
        "PPG signal. What regime am I in, in the EU and the US?",
        "Both the EU and the US. It is software only — no hardware of our own. It analyses the "
        "raw PPG waveform and tells the user to seek review, so yes, it informs a clinical "
        "decision. It does not examine specimens.",
        "Yes, it uses a trained neural network. No existing certification — this is a new product.",
    ],
    # The brief's second example question: the legacy transition branch.
    "mdd_legacy": [
        "I have a Class IIb device CE-marked under MDD. What do I need to do now?",
        "Its intended purpose is to treat chronic spasticity by delivering medication directly "
        "to the spinal fluid. It is an implanted infusion pump with a catheter: no software, "
        "no AI, long-term implantable, surgically invasive. EU only. It does not examine "
        "specimens and it does not inform a diagnosis.",
    ],
    # An ambiguous product: this must end in a question, not a guess.
    "ambiguous": ["I'm building something in health tech. What do I need to do?"],
}

# What each scenario must end up as, checked after the last turn.
EXPECTATIONS: dict[str, str] = {
    "greeting": "idle",
    "out_of_scope": "idle",
    "referral": "referred",
    "ppg_smartwatch": "briefed",
    "mdd_legacy": "briefed",
    "ambiguous": "asks_a_question",
}


def run_scenario(name: str, messages: list[str], *, store: StateStore) -> RegAdvisorState:
    logger.info("=" * 78)
    logger.info("Scenario: %s", name)
    logger.info("=" * 78)

    conversation_id = f"scenario-{name}"
    state = RegAdvisorState()
    for message in messages:
        logger.info("User:      %s", message)
        result = run_chat_turn(message, conversation_id=conversation_id, store=store)
        state = result["state"]
        logger.info("Assistant: %s", result["response"][:400])
        logger.info("Phase:     %s (turn %d)", state.phase.value, state.turn)
    return state


def check(name: str, state: RegAdvisorState) -> bool:
    expected = EXPECTATIONS[name]
    if expected == "asks_a_question":
        last = state.history[-1]["content"] if state.history else ""
        passed = "?" in last and state.phase is not Phase.BRIEFED
        if not passed:
            logger.error("%s: expected a question rather than a briefing, got %r", name, last[:120])
        return passed

    passed = state.phase.value == expected
    if not passed:
        logger.error("%s: expected phase %s, got %s", name, expected, state.phase.value)
    return passed


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    validate_knowledge_base()
    store = StateStore()

    failures: list[str] = []
    for name, messages in SCENARIOS.items():
        try:
            state = run_scenario(name, messages, store=store)
        except RuntimeError as exc:
            logger.error("%s failed: %s", name, exc)
            return 1
        if not check(name, state):
            failures.append(name)

    logger.info("=" * 78)
    if failures:
        logger.error("Failed post-conditions: %s", ", ".join(failures))
        return 1
    logger.info("All %d scenarios met their post-conditions.", len(SCENARIOS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
