"""Microsoft Agent Framework multi-agent travel planner for trace testing."""

from travel_agent.agents import ALL_AGENT_NAMES, SPECIALIST_FACTORIES, create_coordinator
from travel_agent.brief import BriefContextProvider, bind_brief, current_brief
from travel_agent.router import coordinator_directive, eligible_targets, is_conversational
from travel_agent.runner import TurnFailedError, run_turn
from travel_agent.safety import SafetyAction, SafetyVerdict, classify
from travel_agent.session import StateStore, default_store, run_chat_turn, run_chat_turn_sync
from travel_agent.state import (
    Phase,
    Sight,
    TripBrief,
    TripLeg,
    derive_phase,
    missing_slots,
    pending_specialists,
    render_brief,
    render_plan,
)
from travel_agent.workflow import build_travel_workflow, get_participants


def __getattr__(name: str):
    """Lazy import for ``app`` to avoid circular imports with ``__main__``."""
    if name == "app":
        from travel_agent.app import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ALL_AGENT_NAMES",
    "SPECIALIST_FACTORIES",
    "BriefContextProvider",
    "Phase",
    "SafetyAction",
    "SafetyVerdict",
    "Sight",
    "StateStore",
    "TripBrief",
    "TripLeg",
    "TurnFailedError",
    "app",
    "bind_brief",
    "build_travel_workflow",
    "classify",
    "coordinator_directive",
    "create_coordinator",
    "current_brief",
    "default_store",
    "derive_phase",
    "eligible_targets",
    "get_participants",
    "is_conversational",
    "missing_slots",
    "pending_specialists",
    "render_brief",
    "render_plan",
    "run_chat_turn",
    "run_chat_turn_sync",
    "run_turn",
]
