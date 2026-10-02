"""What a conversation remembers between turns: a short record per turn, not the transcript.

Triage only needs enough to rewrite a follow-up into a standalone question, so each turn keeps
its question, route and cited pages, plus any clarification still waiting for a reply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from docs_assistant.schemas import Clarification

HISTORY_TURNS = 6
_NUMBER = re.compile(r"^\s*(?:option\s*|nr\.?\s*|#)?(\d)\s*[.)]?\s*$", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9äöüß]+")
_FILLER = frozenset(
    "the a an in on with via using use i im i'm want to please for my it option der die das "
    "im mit über bitte ich rhesis".split()
)


@dataclass
class TurnRecord:
    question: str
    route: str
    cited_urls: list[str] = field(default_factory=list)


@dataclass
class PendingClarification:
    """A clarifying question we asked, and the question it was about."""

    question: str
    clarification: Clarification
    language: str
    surface: str = "unknown"


@dataclass
class ConversationState:
    conversation_id: str
    turns: list[TurnRecord] = field(default_factory=list)
    pending: PendingClarification | None = None
    # Clarifying questions asked in a row; at the limit, the next turn must answer.
    clarify_streak: int = 0

    @property
    def turn(self) -> int:
        return len(self.turns)

    def history(self, limit: int = HISTORY_TURNS) -> str:
        lines = []
        for record in self.turns[-limit:]:
            cited = f"; cited: {', '.join(record.cited_urls[:4])}" if record.cited_urls else ""
            lines.append(f"- user asked: {record.question} → {record.route}{cited}")
        if self.pending:
            options = "; ".join(self.pending.clarification.options)
            lines.append(
                f"- you asked back: {self.pending.clarification.question} (options: {options})"
            )
        return "\n".join(lines)


def match_option(reply: str, options: list[str]) -> str | None:
    """The option a reply picks, by number ("2", "option 2") or by its words; None if unclear."""
    if match := _NUMBER.match(reply):
        index = int(match.group(1)) - 1
        return options[index] if 0 <= index < len(options) else None
    reply_words = _content_words(reply)
    if not reply_words:
        return None
    scored = []
    for option in options:
        option_words = _content_words(option)
        overlap = len(reply_words & option_words)
        # Every content word of the reply must belong to the option: "the SDK" picks
        # "In the Python SDK", but "the SDK and the UI" is ambiguous and goes to triage.
        if overlap == len(reply_words):
            scored.append((overlap / max(len(option_words), 1), option))
    ranked = sorted(scored, reverse=True)
    if len(ranked) == 1 or (len(ranked) > 1 and ranked[0][0] > ranked[1][0]):
        return ranked[0][1]
    return None


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _FILLER}
