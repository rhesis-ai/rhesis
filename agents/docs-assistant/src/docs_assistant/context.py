"""Per-turn state shared by the tools, passed to the agent as the run context."""

from __future__ import annotations

from dataclasses import dataclass, field

from docs_assistant.config import Settings
from docs_assistant.corpus.cache import CorpusCache, Snapshot
from docs_assistant.corpus.index import SearchHit
from docs_assistant.corpus.parser import Page
from docs_assistant.schemas import AnswerDraft


@dataclass
class Budget:
    tool_calls: int = 0
    pages: int = 0
    searches: int = 0


@dataclass
class TokenMeter:
    """Tokens used across every part of one turn; the token budget is per turn."""

    used: int = 0


@dataclass
class TurnContext:
    snapshot: Snapshot
    settings: Settings
    cache: CorpusCache | None = None
    # Pages the model actually read this turn, keyed by canonical URL. Only these can be cited.
    ledger: dict[str, Page] = field(default_factory=dict)
    budget: Budget = field(default_factory=Budget)
    search_hits: list[SearchHit] = field(default_factory=list)
    accepted: AnswerDraft | None = None
    rejections: int = 0
    # True once submit_answer ran out of retries with nothing salvageable.
    gave_up: bool = False
    # The last answer run's conversation, pages included, so a re-run can continue from it.
    history: list = field(default_factory=list)
    limits_hit: list[str] = field(default_factory=list)
    # False right after a clarifying question: the next answer must not ask another.
    allow_clarify: bool = True
    tokens: TokenMeter = field(default_factory=TokenMeter)
    # Estimated tokens of tool results the next model call will read, so the soft budget sees
    # a batch of reads before that call reports real usage. Reset after every model call.
    pending_tokens: int = 0

    def hit_limit(self, name: str) -> None:
        if name not in self.limits_hit:
            self.limits_hit.append(name)
