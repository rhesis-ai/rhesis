"""Visit-Prep: Haystack multi-agent visit preparation assistant."""

from visit_prep._bootstrap import bootstrap  # noqa: I001 - must precede the Haystack imports

# The pipeline import below pulls in Haystack, which latches its content-tracing flag on import.
bootstrap()

from visit_prep.pipeline import (  # noqa: E402
    build_coordinator_agent,
    build_coordinator_pipeline,
    run_turn,
    run_turn_async,
)
from visit_prep.session import (  # noqa: E402
    StateStore,
    default_store,
    run_chat_turn,
    run_chat_turn_async,
)
from visit_prep.state import CORE_SLOTS, Phase, Slots, VisitPrepState  # noqa: E402


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
    "VisitPrepState",
    "app",
    "build_coordinator_agent",
    "build_coordinator_pipeline",
    "default_store",
    "run_chat_turn",
    "run_chat_turn_async",
    "run_turn",
    "run_turn_async",
]
