"""The in-memory docs snapshot: TTL, background refresh, and stale fallback."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from docs_assistant.corpus.changelog import ChangelogEntry, parse_changelog
from docs_assistant.corpus.fetcher import DocsFetcher, DocsFetchError
from docs_assistant.corpus.index import SearchIndex
from docs_assistant.corpus.parser import (
    IndexEntry,
    Page,
    parse_llms_full,
    parse_llms_txt,
    url_to_path,
)

logger = logging.getLogger(__name__)


class DocsUnavailable(RuntimeError):
    """No snapshot exists and the docs site cannot be reached."""


@dataclass
class Snapshot:
    pages: dict[str, Page]
    entries: list[IndexEntry]
    index: SearchIndex
    changelog: list[ChangelogEntry]
    fetched_at: datetime
    content_hash: str

    def page(self, url_or_path: str) -> Page | None:
        return self.pages.get(url_to_path(url_or_path))

    def entry(self, url: str) -> IndexEntry | None:
        path = url_to_path(url)
        return next((e for e in self.entries if url_to_path(e.url) == path), None)

    def known_url(self, url: str) -> bool:
        return self.page(url) is not None or self.entry(url) is not None


def build_snapshot(llms_txt: str, llms_full: str, fetched_at: datetime | None = None) -> Snapshot:
    pages = {p.path: p for p in parse_llms_full(llms_full)}
    entries = parse_llms_txt(llms_txt)
    changelog_page = pages.get("changelog")
    return Snapshot(
        pages=pages,
        entries=entries,
        index=SearchIndex(list(pages.values()), entries),
        changelog=parse_changelog(changelog_page) if changelog_page else [],
        fetched_at=fetched_at or datetime.now(timezone.utc),
        content_hash=_hash(llms_txt, llms_full),
    )


def _hash(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode())
    return digest.hexdigest()


class CorpusCache:
    def __init__(self, fetcher: DocsFetcher, ttl: int = 3600, clock=time.monotonic) -> None:
        self.fetcher = fetcher
        self.ttl = ttl
        self._clock = clock
        self._snapshot: Snapshot | None = None
        self._loaded_at = 0.0
        self._last_refresh_failed = False
        self._refresh_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def snapshot(self) -> Snapshot | None:
        return self._snapshot

    @property
    def expired(self) -> bool:
        return self._snapshot is not None and self._clock() - self._loaded_at > self.ttl

    @property
    def stale(self) -> bool:
        """Past its TTL and the last refresh failed: answers must say the docs may be old."""
        return self.expired and self._last_refresh_failed

    def status(self) -> str:
        if self._snapshot is None:
            return "unavailable"
        return "stale" if self.stale else "ready"

    async def get(self) -> Snapshot:
        if self._snapshot is None:
            async with self._lock:
                if self._snapshot is None:
                    await self.refresh(raise_on_error=True)
        elif self.expired and not self._refreshing:
            self._refresh_task = asyncio.create_task(self.refresh())
        return self._snapshot

    @property
    def _refreshing(self) -> bool:
        return self._refresh_task is not None and not self._refresh_task.done()

    async def refresh(self, *, raise_on_error: bool = False) -> bool:
        """Fetch and rebuild. Returns False (and keeps the old snapshot) when the site is down."""
        try:
            llms_txt, llms_full = await asyncio.gather(
                self.fetcher.fetch_index(), self.fetcher.fetch_full()
            )
        except DocsFetchError as exc:
            self._last_refresh_failed = True
            logger.warning("Docs refresh failed: %s", exc)
            if raise_on_error and self._snapshot is None:
                raise DocsUnavailable(str(exc)) from exc
            return False
        now = datetime.now(timezone.utc)
        if self._snapshot and self._snapshot.content_hash == _hash(llms_txt, llms_full):
            self._snapshot.fetched_at = now
        else:
            self._snapshot = await asyncio.to_thread(build_snapshot, llms_txt, llms_full, now)
            logger.info("Docs snapshot built: %d pages", len(self._snapshot.pages))
        self._loaded_at = self._clock()
        self._last_refresh_failed = False
        return True

    async def fetch_live_page(self, url_or_path: str, timeout: float) -> str:
        return await self.fetcher.fetch_page(url_or_path, timeout=timeout)
