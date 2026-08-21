"""Shared harness for the traced scenario entry points.

The two traced variants — ``run_scenarios_traced_native.py`` and
``run_scenarios_traced_upstream.py`` — differ only in which ``RhesisTracing`` class they import.
Everything else about running the canned scenarios under tracing lives here, so the integrations
stay separated without the harness drifting between them.

This module imports nothing from Haystack or either integration, which is what lets a variant
import it *before* choosing an integration and still control import ordering.
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Protocol

EXAMPLES_DIR = Path(__file__).resolve().parent
TURN_SPAN_NAME = "function.visit_prep_turn"

logger = logging.getLogger("visit_prep.examples.traced")


class TracingFactory(Protocol):
    """The slice of ``RhesisTracing`` this harness needs. Both integrations satisfy it."""

    def __call__(self, name: str, *, turn_span_name: str = ...) -> Any: ...


def bootstrap() -> None:
    """Load ``.env`` and switch Haystack content tracing on.

    Call this before importing an integration. Haystack reads
    ``HAYSTACK_CONTENT_TRACING_ENABLED`` once, when it is imported, and the upstream integration
    imports Haystack at module level — so setting it afterwards would silently produce spans with
    no prompts or completions.
    """
    from dotenv import load_dotenv

    load_dotenv()
    os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "true")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def run_traced_scenarios(tracing_cls: TracingFactory, *, label: str) -> int:
    """Run every canned scenario with each turn wrapped in a Rhesis turn span.

    One conversation per scenario, so each lands in its own trace.

    :param tracing_cls: The ``RhesisTracing`` class of the integration to trace through.
    :param label: Integration name, used in log messages so a trace can be attributed.
    """
    if str(EXAMPLES_DIR) not in sys.path:
        sys.path.insert(0, str(EXAMPLES_DIR))

    from run_scenarios import SCENARIOS, check_terminal_phase, run_scenario

    from visit_prep.pipeline import build_coordinator_pipeline

    tracing = tracing_cls("Visit-Prep", turn_span_name=TURN_SPAN_NAME)
    if not tracing.enabled:
        logger.error(
            "Rhesis tracing (%s) is not configured. Set RHESIS_API_KEY in .env (see .env.example).",
            label,
        )
        return 1

    try:
        pipeline = build_coordinator_pipeline()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    try:
        for name, messages in SCENARIOS.items():
            tracing.start_conversation(str(uuid.uuid4()))
            final_state = run_scenario(name, messages, pipeline=pipeline, turn_hook=tracing.turn)
            error = check_terminal_phase(name, final_state)
            if error:
                logger.error("%s", error)
                return 1
        logger.info("All traced scenarios completed (%s integration).", label)
        return 0
    finally:
        tracing.flush()
