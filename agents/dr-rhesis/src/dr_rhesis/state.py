"""Shared state for the Dr-Rhesis agent."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# Core OPQRST / SOCRATES slots required for a "complete" history.
# ``context`` (meds, conditions, recent changes) is optional for the first draft
# so gathering can finish without probing background history on every visit.
CORE_SLOTS: tuple[str, ...] = (
    "onset",
    "location",
    "character",
    "severity",
    "timing",
    "aggravating",
    "relieving",
    "associated",
)


class Phase(str, Enum):
    IDLE = "idle"
    GATHERING = "gathering"
    DONE = "done"
    ESCALATED = "escalated"


class Slots(BaseModel):
    onset: str | None = None
    location: str | None = None
    character: str | None = None
    severity: str | None = None
    timing: str | None = None
    aggravating: str | None = None
    relieving: str | None = None
    associated: str | None = None
    context: str | None = None


class DrRhesisState(BaseModel):
    turn: int = 0
    phase: Phase = Phase.IDLE
    chief_complaint: str | None = None
    slots: Slots = Field(default_factory=Slots)
    history: list[dict[str, str]] = Field(default_factory=list)
    red_flag: bool = False


def missing_core_slots(state: DrRhesisState) -> list[str]:
    """Return core slot names that are still unset."""
    return [name for name in CORE_SLOTS if getattr(state.slots, name) is None]


def apply_slot_updates(state: DrRhesisState, updates: dict[str, str | None]) -> DrRhesisState:
    """Merge non-null slot updates into a copy of state."""
    new_state = state.model_copy(deep=True)
    for key, value in updates.items():
        if value is not None and hasattr(new_state.slots, key):
            setattr(new_state.slots, key, value)
    return new_state


__all__ = [
    "CORE_SLOTS",
    "Phase",
    "Slots",
    "DrRhesisState",
    "apply_slot_updates",
    "missing_core_slots",
]
