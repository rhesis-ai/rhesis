"""The docs corpus: fetch, parse, index and cache the live docs site."""

from docs_assistant.corpus.cache import CorpusCache, DocsUnavailable, Snapshot, build_snapshot
from docs_assistant.corpus.fetcher import DocsFetcher, DocsFetchError
from docs_assistant.corpus.parser import Page, canonical_url

__all__ = [
    "CorpusCache",
    "DocsFetchError",
    "DocsFetcher",
    "DocsUnavailable",
    "Page",
    "Snapshot",
    "build_snapshot",
    "canonical_url",
]
