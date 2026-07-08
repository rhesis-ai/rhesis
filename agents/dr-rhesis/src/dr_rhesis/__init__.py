"""Dr-Rhesis: Haystack multi-agent visit preparation assistant."""

from dr_rhesis.pipeline import (
    TurnComponents,
    build_intent_pipeline,
    build_turn_components,
    run_turn,
)
from dr_rhesis.session import StateStore, default_store, run_chat_turn
from dr_rhesis.state import CORE_SLOTS, Phase, Slots, DrRhesisState


def __getattr__(name: str):
    if name == "app":
        from dr_rhesis.app import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CORE_SLOTS",
    "Phase",
    "Slots",
    "StateStore",
    "TurnComponents",
    "DrRhesisState",
    "app",
    "build_intent_pipeline",
    "build_turn_components",
    "default_store",
    "run_chat_turn",
    "run_turn",
]
