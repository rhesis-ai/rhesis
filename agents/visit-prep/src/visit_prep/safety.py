"""Red-flag detection for Visit-Prep."""

from __future__ import annotations

import re
from collections.abc import Iterable

from haystack.dataclasses import ChatMessage

from visit_prep.utils import user_texts

# Rule-based patterns for potentially emergent presentations.
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


def first_red_flag_text(messages: Iterable[ChatMessage]) -> str | None:
    """Return the first user message that matches a red-flag pattern, or ``None``.

    Only the user's own words are scanned: the assistant's escalation wording and tool
    results must not re-trigger the check. Because the coordinator replays the whole
    conversation every turn, a red flag raised on an earlier turn keeps matching — which
    is what makes escalation sticky.
    """
    for text in user_texts(messages):
        if text_suggests_red_flag(text):
            return text
    return None


__all__ = [
    "RED_FLAG_PATTERNS",
    "first_red_flag_text",
    "text_suggests_red_flag",
]
