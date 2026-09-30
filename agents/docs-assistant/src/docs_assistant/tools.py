"""The answer agent's tools.

Each tool has a plain implementation taking a `TurnContext` (what the tests call) and a thin
`@function_tool` wrapper the model sees. Read tools charge the turn budget; `submit_answer` never
does, so the model can always hand in what it has.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from agents import RunContextWrapper, function_tool

from docs_assistant import grounding
from docs_assistant.context import TurnContext
from docs_assistant.corpus.changelog import select_entries
from docs_assistant.corpus.fetcher import DocsFetchError
from docs_assistant.corpus.parser import Page, canonical_url, parse_page_markdown
from docs_assistant.schemas import AnswerDraft

logger = logging.getLogger(__name__)

DocsSection = Literal[
    "docs", "sdk", "guides", "self_hosting", "glossary", "changelog", "contribute"
]

ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
NOT_FOUND = "NOT_FOUND"
MAX_SEARCH_RESULTS = 10
MAX_LISTED_ENTRIES = 80
CHANGELOG_ENTRY_CHARS = 3000
_DEPRECATION = re.compile(r"deprecated|legacy|no longer|removed in", re.IGNORECASE)


def _over_budget(ctx: TurnContext, kind: str | None = None) -> str | None:
    """Charge one tool call (and one `kind`) to the budget; return a message once it runs out."""
    limits = ctx.settings
    ctx.budget.tool_calls += 1
    if ctx.budget.tool_calls > limits.max_tool_calls:
        ctx.hit_limit("tool_budget")
        return (
            f"{BUDGET_EXHAUSTED}: you have used all {limits.max_tool_calls} tool calls for this "
            "question. Call submit_answer now with what you have read."
        )
    if kind == "search" and ctx.budget.searches >= limits.max_searches:
        ctx.hit_limit("search_budget")
        return f"{BUDGET_EXHAUSTED}: no searches left. Read the pages you found, then submit."
    if kind == "search":
        ctx.budget.searches += 1
    return None


# ── search_docs ──────────────────────────────────────────────────────────────────────────


def search_docs_impl(ctx: TurnContext, query: str, section: str | None = None, k: int = 6) -> str:
    if message := _over_budget(ctx, "search"):
        return message
    hits = ctx.snapshot.index.search(query, section=section, k=max(1, min(k, MAX_SEARCH_RESULTS)))
    ctx.search_hits.extend(hits)
    if not hits:
        return "No matching sections. Try other words, or list_sections to browse."
    lines = ["Search results (snippets are NOT citable; fetch_page a result to cite it):"]
    for hit in hits:
        url = f"{hit.url}#{hit.anchor}" if hit.anchor else hit.url
        lines.append(f"- {url} — {hit.title} › {hit.heading} [{hit.section}]\n  {hit.snippet}")
    return "\n".join(lines)


@function_tool
def search_docs(
    ctx: RunContextWrapper[TurnContext],
    query: str,
    section: DocsSection | None,
    k: int,
) -> str:
    """Search the Rhesis documentation by keywords.

    Args:
        query: Keywords, including exact names such as class names or env vars.
        section: Limit to one docs section, or null to search everything.
        k: How many results to return (1-10). 6 is a good default.
    """
    return search_docs_impl(ctx.context, query, section, k)


# ── fetch_page ───────────────────────────────────────────────────────────────────────────


async def fetch_page_impl(
    ctx: TurnContext, url_or_path: str, section_anchor: str | None = None
) -> str:
    if message := _over_budget(ctx):
        return message
    url = canonical_url(url_or_path)
    first_read = url not in ctx.ledger
    if first_read and ctx.budget.pages >= ctx.settings.max_pages:
        ctx.hit_limit("page_budget")
        return (
            f"{BUDGET_EXHAUSTED}: you have read {ctx.settings.max_pages} pages, the limit. "
            "Submit with what you have read."
        )
    page = ctx.ledger.get(url) or await _load_page(ctx, url)
    if page is None:
        return _not_found(ctx, url_or_path)
    if first_read:
        ctx.budget.pages += 1
        ctx.ledger[url] = page
    return render_page(page, section_anchor, ctx.settings.page_window_chars)


async def _load_page(ctx: TurnContext, url: str) -> Page | None:
    page = ctx.snapshot.page(url)
    # Go live when the snapshot is past its TTL, or for pages the index lists but the full corpus
    # lacks (llms-full.txt currently leaves out the generated glossary pages).
    wants_live = ctx.cache is not None and (ctx.cache.expired or page is None)
    if not wants_live or not ctx.snapshot.known_url(url):
        return page
    try:
        text = await ctx.cache.fetch_live_page(url, timeout=ctx.settings.page_timeout)
    except DocsFetchError as exc:
        logger.info("Live fetch of %s failed, using the snapshot: %s", url, exc)
        return page
    return parse_page_markdown(text) or page


def _not_found(ctx: TurnContext, url_or_path: str) -> str:
    words = re.sub(r"[/_\-#.]+", " ", url_or_path)
    nearest = ctx.snapshot.index.search(words, k=5) if words.strip() else []
    lines = [f"{NOT_FOUND}: no docs page at {url_or_path}."]
    if nearest:
        lines.append("Closest pages:")
        lines += [f"- {hit.url} — {hit.title}" for hit in nearest]
    return "\n".join(lines)


def render_page(page: Page, section_anchor: str | None, window: int) -> str:
    content, note = _page_window(page, section_anchor, window)
    headings = "\n".join(
        f"  #{s.anchor} {s.heading}" for s in page.sections if s.anchor and s.level <= 3
    )
    hints = [line.strip() for line in page.body.splitlines() if _DEPRECATION.search(line)][:5]
    parts = [f'<doc url="{page.url}" title="{page.title}">']
    if headings:
        parts.append(f"Headings (cite as {page.url}#anchor):\n{headings}")
    if hints:
        parts.append("Possibly deprecated or outdated:\n" + "\n".join(f"  {h}" for h in hints))
    if page.links:
        links = "\n".join(f"  {link.text}: {link.url}" for link in page.links[:30])
        parts.append(f"Links on this page:\n{links}")
    parts += ["---", content]
    if note:
        parts.append(note)
    parts.append("</doc>")
    return "\n".join(parts)


def _page_window(page: Page, anchor: str | None, window: int) -> tuple[str, str | None]:
    index = page.find_section(anchor) if anchor else None
    if index is not None:
        chosen = page.sections[max(index - 1, 0) : index + 2]
        text = "\n\n".join(s.text for s in chosen)
        return text[:window], None
    if len(page.body) <= window:
        return page.body, None
    note = "[Page truncated. Call fetch_page again with section_anchor set to a heading above.]"
    return page.body[:window], note


@function_tool
async def fetch_page(
    ctx: RunContextWrapper[TurnContext], url_or_path: str, section_anchor: str | None
) -> str:
    """Read a docs page as markdown. Only pages read with this tool may be cited.

    Args:
        url_or_path: A docs URL or path, e.g. "https://docs.rhesis.ai/sdk/metrics" or "sdk/metrics".
        section_anchor: A heading anchor to read just that part of a long page, or null.
    """
    return await fetch_page_impl(ctx.context, url_or_path, section_anchor)


# ── list_sections ────────────────────────────────────────────────────────────────────────


def list_sections_impl(ctx: TurnContext, section: str | None = None) -> str:
    if message := _over_budget(ctx):
        return message
    entries = ctx.snapshot.entries
    if not section:
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry.section] = counts.get(entry.section, 0) + 1
        return "Docs sections (pages): " + ", ".join(f"{s} ({n})" for s, n in counts.items())
    chosen = [e for e in entries if e.section == section][:MAX_LISTED_ENTRIES]
    if not chosen:
        return f"No pages in section {section}."
    return "\n".join(f"- {e.url} — {e.title}: {e.description}" for e in chosen)


@function_tool
def list_sections(ctx: RunContextWrapper[TurnContext], section: DocsSection | None) -> str:
    """Browse the docs table of contents.

    Args:
        section: A section to list its pages, or null for the list of sections.
    """
    return list_sections_impl(ctx.context, section)


# ── get_changelog ────────────────────────────────────────────────────────────────────────


def get_changelog_impl(
    ctx: TurnContext,
    version: str | None = None,
    since: str | None = None,
    query: str | None = None,
) -> str:
    if message := _over_budget(ctx):
        return message
    page = ctx.snapshot.page("changelog")
    entries = select_entries(ctx.snapshot.changelog, version=version, since=since, query=query)
    if page is None or not entries:
        return "No matching changelog entries."
    # Reading the changelog counts as reading its page, so its versions can be cited.
    if page.url not in ctx.ledger:
        ctx.ledger[page.url] = page
        ctx.budget.pages += 1
    blocks = [
        f"## {e.version} ({e.date or 'undated'}) — cite as {page.url}#{e.anchor}\n"
        f"{e.body[:CHANGELOG_ENTRY_CHARS]}"
        for e in entries
    ]
    return f'<doc url="{page.url}" title="{page.title}">\n' + "\n\n".join(blocks) + "\n</doc>"


@function_tool
def get_changelog(
    ctx: RunContextWrapper[TurnContext],
    version: str | None,
    since: str | None,
    query: str | None,
) -> str:
    """Read release notes. With all arguments null, returns the latest releases.

    Args:
        version: One version, e.g. "0.13.0", or null.
        since: Only versions newer than this one, e.g. "0.12.0", or null.
        query: Keywords to filter entries, or null.
    """
    return get_changelog_impl(ctx.context, version, since, query)


# ── submit_answer ────────────────────────────────────────────────────────────────────────


def submit_answer_impl(ctx: TurnContext, draft: AnswerDraft) -> str:
    problems = grounding.validate(draft, ctx.ledger)
    if problems:
        ctx.rejections += 1
        numbered = "\n".join(f"{n}. {p}" for n, p in enumerate(problems, start=1))
        return f"{REJECTED}. Fix these and call submit_answer again:\n{numbered}"
    ctx.accepted = draft
    return ACCEPTED


@function_tool
def submit_answer(ctx: RunContextWrapper[TurnContext], draft: AnswerDraft) -> str:
    """Hand in the final answer. Returns ACCEPTED, or REJECTED with problems to fix.

    Args:
        draft: The complete answer with its route, claims and citations.
    """
    return submit_answer_impl(ctx.context, draft)


ANSWER_TOOLS = [search_docs, fetch_page, list_sections, get_changelog, submit_answer]
