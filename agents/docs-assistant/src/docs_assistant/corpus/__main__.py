"""Dev CLI for the docs corpus.

uv run python -m docs_assistant.corpus stats
uv run python -m docs_assistant.corpus search "single-turn vs multi-turn metric"
uv run python -m docs_assistant.corpus changelog --latest
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from docs_assistant.config import get_settings
from docs_assistant.corpus.cache import CorpusCache, DocsUnavailable, Snapshot
from docs_assistant.corpus.changelog import select_entries
from docs_assistant.corpus.fetcher import DocsFetcher


def _stats(snapshot: Snapshot, _args) -> None:
    sections = sum(len(p.sections) for p in snapshot.pages.values())
    print(
        f"{len(snapshot.pages)} pages · {len(snapshot.entries)} index entries · "
        f"{sections} sections · {len(snapshot.changelog)} changelog versions · "
        f"fetched {snapshot.fetched_at.isoformat(timespec='seconds')}"
    )


def _search(snapshot: Snapshot, args) -> None:
    for hit in snapshot.index.search(args.query, section=args.section, k=args.k):
        url = f"{hit.url}#{hit.anchor}" if hit.anchor else hit.url
        print(f"{hit.score:7.2f}  {url}\n         {hit.title} › {hit.heading}")


def _changelog(snapshot: Snapshot, args) -> None:
    limit = 1 if args.latest else 5
    for entry in select_entries(snapshot.changelog, since=args.since, limit=limit):
        print(f"{entry.version} ({entry.date or 'undated'})  #{entry.anchor}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m docs_assistant.corpus")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("stats", help="page, section and index counts")
    search = commands.add_parser("search", help="run a BM25 query")
    search.add_argument("query")
    search.add_argument("--section")
    search.add_argument("-k", type=int, default=6)
    changelog = commands.add_parser("changelog", help="list changelog versions")
    changelog.add_argument("--latest", action="store_true")
    changelog.add_argument("--since")
    args = parser.parse_args()

    settings = get_settings()
    fetcher = DocsFetcher(settings.docs_base_url, timeout=settings.fetch_timeout)
    try:
        snapshot = asyncio.run(CorpusCache(fetcher, ttl=settings.cache_ttl).get())
    except DocsUnavailable as exc:
        print(f"Docs unavailable: {exc}", file=sys.stderr)
        return 1
    {"stats": _stats, "search": _search, "changelog": _changelog}[args.command](snapshot, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
