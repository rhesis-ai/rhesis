"""Runtime settings, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache

# Citations always point at the public site, even when DOCS_BASE_URL fetches from a mirror.
PUBLIC_DOCS_URL = "https://docs.rhesis.ai"


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


@dataclass(frozen=True)
class Settings:
    docs_base_url: str
    fetch_timeout: float
    page_timeout: float
    cache_ttl: int
    max_tool_calls: int
    max_pages: int
    max_searches: int
    max_turns: int
    turn_timeout: float
    token_budget: int
    page_window_chars: int

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            docs_base_url=os.getenv("DOCS_BASE_URL", PUBLIC_DOCS_URL).rstrip("/"),
            fetch_timeout=_float("DOCS_FETCH_TIMEOUT", 10.0),
            page_timeout=_float("DOCS_PAGE_TIMEOUT", 3.0),
            cache_ttl=_int("DOCS_CACHE_TTL", 3600),
            max_tool_calls=_int("DOCS_ASSISTANT_MAX_TOOL_CALLS", 10),
            max_pages=_int("DOCS_ASSISTANT_MAX_PAGES", 6),
            max_searches=_int("DOCS_ASSISTANT_MAX_SEARCHES", 5),
            max_turns=_int("DOCS_ASSISTANT_MAX_TURNS", 12),
            turn_timeout=_float("DOCS_ASSISTANT_TURN_TIMEOUT", 45.0),
            token_budget=_int("DOCS_ASSISTANT_TOKEN_BUDGET", 60_000),
            # About 6K tokens of page text per fetch.
            page_window_chars=_int("DOCS_ASSISTANT_PAGE_WINDOW_CHARS", 24_000),
        )


@cache
def get_settings() -> Settings:
    return Settings.from_env()
