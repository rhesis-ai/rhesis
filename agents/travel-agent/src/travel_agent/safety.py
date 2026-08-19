"""Scope and prompt-injection guard.

Runs in Python before the model sees anything, because a prompt is not an enforcement
mechanism: asking a small model to refuse reliably is exactly the kind of instruction it
drops. A blocked turn never reaches the workflow at all, so a jailbreak attempt costs no
LLM calls and cannot be talked past.

Mixed messages are deliberately not blocked. "Who won the World Cup? Also I like modern
art" still carries real planning content, so it is flagged and the coordinator is told to
decline that part and carry on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from travel_agent.state import TripBrief

_flags = re.IGNORECASE


class SafetyAction(str, Enum):
    ALLOW = "allow"
    FLAG = "flag"
    BLOCK = "block"


@dataclass(frozen=True)
class SafetyVerdict:
    action: SafetyAction
    topic: str = ""

    @property
    def blocked(self) -> bool:
        return self.action is SafetyAction.BLOCK


INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, _flags)
    for pattern in (
        r"\bignore\s+(all\s+)?(your\s+)?(previous|prior|above|earlier)\s+instructions?\b",
        r"\bdisregard\s+(all\s+)?(your\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?)\b",
        # Allows a couple of adjectives before the noun: "your internal system instructions".
        r"\b(reveal|show|print|repeat|output|display|list)\s+(me\s+)?(your|the)\s+"
        r"(\w+\s+){0,2}(prompt|instructions?|configuration|config|tools?)\b",
        r"\bwhat\s+(are|is)\s+your\s+(\w+\s+){0,2}(prompt|instructions?|rules?)\b",
        r"\byou\s+are\s+now\s+(a|an)\b",
        r"\b(pretend|act)\s+(to\s+be|as)\s+(a|an)\b",
        r"\b(developer|god)\s+mode\b",
        r"\bjailbreak\b",
    )
)

# Capabilities this agent does not have. Kept tight on purpose: anything fuzzier is left
# to the coordinator's redirect_to_scope tool, which can decline and keep planning.
OFF_TOPIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "programming or software development",
        re.compile(
            r"\b(write|generate|debug|fix|refactor)\s+(me\s+)?"
            r"(a|an|some|this|that|my|the)?\s*"
            r"(python|javascript|typescript|java|c\+\+|rust|go|sql|bash|shell)?\s*"
            r"(script|code|program|function|class|query|regex)\b|\bfibonacci\b|\balgorithm\b",
            _flags,
        ),
    ),
    (
        "sports results or trivia",
        re.compile(
            r"\bwho\s+won\b|\bwhat\s+year\s+did\b|\bfinal\s+score\b|\bworld\s+cup\s+(winner|final)\b",
            _flags,
        ),
    ),
    (
        "medical advice",
        re.compile(r"\b(diagnos\w+|prescri\w+|symptoms?\s+of|treat\w*\s+my)\b", _flags),
    ),
    (
        "legal or financial advice",
        re.compile(
            r"\b(lawsuit|sue\s+\w+|legal\s+advice|invest\s+in|stock\s+market|tax\s+advice)\b",
            _flags,
        ),
    ),
)

TRAVEL_PATTERNS: re.Pattern[str] = re.compile(
    r"\b(trip|travel|visit|itinerar\w+|destination|vacation|holiday|sightsee\w*|"
    r"tour|flight|hotel|hostel|museum|restaurant|city|days?|weekend|going\s+to|"
    r"go\s+to|stay\s+in|budget|pack\w*|weather)\b",
    _flags,
)

BLOCK_REPLIES: dict[str, str] = {
    "injection": (
        "I'm a travel planning assistant, and I can't share my system configuration or take on "
        "another role. I'd be glad to help you plan a trip though - where would you like to go?"
    ),
}


def _off_topic_topic(message: str) -> str:
    for topic, pattern in OFF_TOPIC_PATTERNS:
        if pattern.search(message):
            return topic
    return ""


def _mentions_travel(message: str) -> bool:
    return bool(TRAVEL_PATTERNS.search(message))


def classify(message: str, brief: TripBrief | None = None) -> SafetyVerdict:
    """Decide whether a message is safe to plan against, needs a caveat, or must be refused."""
    text = message or ""

    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return SafetyVerdict(SafetyAction.BLOCK, "injection")

    topic = _off_topic_topic(text)
    if not topic:
        return SafetyVerdict(SafetyAction.ALLOW)

    # Off-topic alongside a live trip, or alongside travel words, is a mixed message:
    # decline that part and keep planning rather than refusing the whole turn.
    has_trip = bool(brief and brief.legs)
    if has_trip or _mentions_travel(text):
        return SafetyVerdict(SafetyAction.FLAG, topic)
    return SafetyVerdict(SafetyAction.BLOCK, topic)


def refusal_for(verdict: SafetyVerdict) -> str:
    """The deterministic reply served for a blocked turn."""
    if verdict.topic in BLOCK_REPLIES:
        return BLOCK_REPLIES[verdict.topic]
    return (
        f"I can't assist with {verdict.topic}. I can only help with travel planning - "
        "itineraries, destination research, weather, travel times and trip budgets. "
        "Let me know if you have a destination in mind!"
    )


def flag_note(verdict: SafetyVerdict) -> str:
    """Instruction appended for a flagged turn, telling the coordinator to decline and continue."""
    return (
        f"SCOPE NOTE: part of this message asks about {verdict.topic}, which is out of scope. "
        f"Call redirect_to_scope with topic='{verdict.topic}' and a follow_up that continues the "
        "trip already on file. Answer nothing about that topic."
    )


__all__ = [
    "BLOCK_REPLIES",
    "INJECTION_PATTERNS",
    "OFF_TOPIC_PATTERNS",
    "SafetyAction",
    "SafetyVerdict",
    "classify",
    "flag_note",
    "refusal_for",
]
