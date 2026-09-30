"""Shared fixtures: a docs site served from tests/fixtures, with no network."""

from __future__ import annotations

import os
import re
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

# Keep the suite hermetic, as the sibling agents do: no Rhesis connector from a local .env.
os.environ["RHESIS_API_KEY"] = ""
os.environ["RHESIS_PROJECT_ID"] = ""

from docs_assistant.config import Settings  # noqa: E402
from docs_assistant.context import TurnContext  # noqa: E402
from docs_assistant.corpus.cache import CorpusCache, build_snapshot  # noqa: E402
from docs_assistant.corpus.fetcher import DocsFetcher  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
LLMS_TXT = (FIXTURES / "llms.txt").read_text()
LLMS_FULL = (FIXTURES / "llms-full.txt").read_text()
BASE = "https://docs.rhesis.ai"

# Served by /api/md/ for pages the full corpus leaves out, like the live glossary pages.
EXTRA_PAGES = {
    "glossary/hallucination": (
        "---\nurl: https://docs.rhesis.ai/glossary/hallucination\ntitle: Hallucination\n---\n"
        "# Hallucination\n\nWhen an LLM generates false, fabricated, or nonsensical information "
        "presented as fact, often with high confidence.\n"
    )
}


def page_blocks(full: str) -> dict[str, str]:
    starts = [m.start() for m in re.finditer(r"^---\nurl: ", full, re.MULTILINE)]
    blocks = {}
    for i, start in enumerate(starts):
        block = full[start : starts[i + 1] if i + 1 < len(starts) else len(full)]
        path = re.match(r"---\nurl: (\S+)", block).group(1).removeprefix(f"{BASE}/")
        blocks[path] = block
    return blocks


class FakeDocsSite:
    """An httpx transport that serves the fixture files and counts requests."""

    def __init__(self, llms_txt: str = LLMS_TXT, llms_full: str = LLMS_FULL) -> None:
        self.llms_txt = llms_txt
        self.llms_full = llms_full
        self.down = False
        self.requests: list[str] = []
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append(path)
        if self.down:
            raise httpx.ConnectError("docs site down", request=request)
        if path == "/llms.txt":
            return httpx.Response(200, text=self.llms_txt)
        if path == "/llms-full.txt":
            return httpx.Response(200, text=self.llms_full)
        if path.startswith("/api/md/"):
            slug = path.removeprefix("/api/md/")
            body = {**page_blocks(self.llms_full), **EXTRA_PAGES}.get(slug)
            return httpx.Response(200, text=body) if body else httpx.Response(404, text="# 404")
        return httpx.Response(404)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def settings() -> Settings:
    base = Settings.from_env()
    return replace(base, docs_base_url=BASE, fetch_timeout=1.0, page_timeout=1.0, cache_ttl=3600)


@pytest.fixture
def snapshot():
    return build_snapshot(LLMS_TXT, LLMS_FULL)


@pytest.fixture
def site() -> FakeDocsSite:
    return FakeDocsSite()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def cache(site, clock) -> CorpusCache:
    fetcher = DocsFetcher(BASE, timeout=1.0, retries=0, transport=site.transport)
    return CorpusCache(fetcher, ttl=3600, clock=clock)


@pytest.fixture
def ctx(snapshot, settings) -> TurnContext:
    return TurnContext(snapshot=snapshot, settings=settings)
