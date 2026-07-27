"""Visit-Prep: Haystack multi-agent visit preparation assistant."""

from visit_prep.pipeline import (
    TurnComponents,
    build_intent_pipeline,
    build_turn_components,
    run_turn,
)
from visit_prep.session import StateStore, default_store, run_chat_turn
from visit_prep.state import CORE_SLOTS, Phase, Slots, VisitPrepState


def __getattr__(name: str):
    if name == "app":
        from visit_prep.app import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CORE_SLOTS",
    "Phase",
    "Slots",
    "StateStore",
    "TurnComponents",
    "VisitPrepState",
    "app",
    "build_intent_pipeline",
    "build_turn_components",
    "default_store",
    "run_chat_turn",
    "run_turn",
]
