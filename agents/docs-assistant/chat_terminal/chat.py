"""Interactive terminal chat with the Docs Assistant.

Run from the project root:

    uv run python chat_terminal/chat.py

or with the launcher:

    chat_terminal/run
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from docs_assistant.app import make_cache  # noqa: E402
from docs_assistant.corpus.cache import DocsUnavailable  # noqa: E402
from docs_assistant.runner import run_turn  # noqa: E402

QUIT = {"quit", "exit", "q", "/quit", "/exit", "/q"}
HELP = {"help", "/help", "?"}

BANNER = """
──────────────────────────────────────────────────────────────────────────────
 Docs Assistant — answers from https://docs.rhesis.ai, with citations
──────────────────────────────────────────────────────────────────────────────
 Ask anything about Rhesis. Commands: help · quit
""".strip()

HELP_TEXT = """
What I do
  Answer questions about Rhesis from the live docs. Every claim cites a page I
  read during the turn; if the docs don't cover something, I say so.

Commands
  help   show this
  quit   leave
""".strip()


async def chat_loop() -> int:
    cache = make_cache()
    try:
        snapshot = await cache.get()
    except DocsUnavailable as exc:
        print(f"The docs site can't be reached and nothing is cached: {exc}")
        return 1
    print(BANNER)
    fetched = f"{snapshot.fetched_at:%Y-%m-%d %H:%M} UTC"
    print(f"\nDocs: {len(snapshot.pages)} pages, fetched {fetched}.\n")

    while True:
        try:
            message = (await asyncio.to_thread(input, "you: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0
        if not message:
            continue
        if message.lower() in QUIT:
            print("Bye.")
            return 0
        if message.lower() in HELP:
            print(f"\n{HELP_TEXT}\n")
            continue

        try:
            response = await run_turn(message, cache=cache)
        except RuntimeError as exc:
            print(f"\n{exc}\n")
            return 1
        print(f"\ndocs-assistant: {response.response}\n")
        limits = f", limits={','.join(response.limits_hit)}" if response.limits_hit else ""
        stale = ", STALE" if response.docs_stale else ""
        print(
            f"[route={response.route.value}, citations={len(response.citations)}, "
            f"docs as of {response.docs_as_of:%Y-%m-%d %H:%M} UTC{stale}{limits}]\n"
        )


def main() -> int:
    return asyncio.run(chat_loop())


if __name__ == "__main__":
    sys.exit(main())
