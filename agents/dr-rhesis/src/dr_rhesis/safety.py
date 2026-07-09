"""Red-flag detection for Dr-Rhesis."""

from __future__ import annotations

import re

from haystack import component

from dr_rhesis.state import DrRhesisState

# Rule-based patterns for potentially emergent presentations.
# A future ``tools.py`` extension point could wire a "find care near me" lookup
# only into the escalation path — not implemented in this draft.
RED_FLAG_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bchest pain\b",
        r"\bcan(?:'|no)t breathe\b|\bshortness of breath\b|\btrouble breathing\b",
        r"\bunconscious\b|\bpassed out\b|\blost consciousness\b",
        r"\bstroke\b|\bface droop\b|\bslurred speech\b|\bnumbness on one side\b",
        r"\bsevere bleeding\b|\buncontrolled bleeding\b",
        r"\bsuicid(e|al)\b|\bkill myself\b|\bwant to die\b",
        r"\bworst headache\b|\bsudden severe headache\b|\bthunderclap headache\b",
        r"\bheart attack\b",
        r"\bseizure\b|\bconvulsions\b",
        r"\bpoison(ing|ed)\b|\boverdose\b",
        r"\bsevere allergic reaction\b|\banaphylaxis\b|\bthroat (is )?closing\b",
    )
)


def text_suggests_red_flag(text: str) -> bool:
    """Return True if free text matches any red-flag pattern."""
    return any(pattern.search(text) for pattern in RED_FLAG_PATTERNS)


def has_red_flag(state: DrRhesisState) -> bool:
    """Evaluate the accumulated picture for red-flag phrases."""
    if state.red_flag:
        return True
    chunks: list[str] = []
    if state.chief_complaint:
        chunks.append(state.chief_complaint)
    for slot_name in (
        "onset",
        "location",
        "character",
        "severity",
        "timing",
        "aggravating",
        "relieving",
        "associated",
        "context",
    ):
        value = getattr(state.slots, slot_name)
        if value:
            chunks.append(value)
    for message in state.history:
        chunks.append(message.get("content", ""))
    combined = "\n".join(chunks)
    return text_suggests_red_flag(combined)


@component
class RedFlagChecker:
    """Haystack component wrapper around :func:`has_red_flag`."""

    @component.output_types(red_flag=bool)
    def run(self, state: DrRhesisState) -> dict[str, bool]:
        return {"red_flag": has_red_flag(state)}


__all__ = [
    "RED_FLAG_PATTERNS",
    "RedFlagChecker",
    "has_red_flag",
    "text_suggests_red_flag",
]
