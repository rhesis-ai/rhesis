"""Turn the parts of a turn into the reply text, the typed citations and the turn route."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

from docs_assistant import terminals
from docs_assistant.corpus.cache import Snapshot
from docs_assistant.corpus.parser import split_anchor
from docs_assistant.schemas import (
    AnswerDraft,
    Citation,
    Clarification,
    NextStep,
    RelatedPage,
    Route,
)

_MARKER = re.compile(r"\[([\w-]+(?:\s*,\s*[\w-]+)*)\](?!\()")
_CODE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`", re.DOTALL)

# Most severe first. When parts disagree and none was (partly) answered, the turn takes the
# most severe route among them.
SEVERITY = [
    Route.UNSAFE_OR_INJECTION,
    Route.ACCOUNT_OR_SUPPORT,
    Route.OUT_OF_SCOPE,
    Route.SMALLTALK,
    Route.NEEDS_CLARIFICATION,
    Route.FALSE_PREMISE,
    Route.NOT_DOCUMENTED,
    Route.PARTIALLY_ANSWERED,
    Route.ANSWERED,
]


@dataclass
class PartOutcome:
    """One part of a turn: a checked draft for docs parts, fixed text for the others."""

    question: str
    route: Route
    draft: AnswerDraft | None = None
    text: str = ""
    citations: list[Citation] = field(default_factory=list)
    related: list[RelatedPage] = field(default_factory=list)
    # Pages that code in the answer was adapted from (not copied verbatim).
    adapted: list[RelatedPage] = field(default_factory=list)


def turn_route(routes: list[Route]) -> Route:
    """One route for the turn: the shared one; else partial if anything was answered; else the
    most severe."""
    if len(set(routes)) == 1:
        return routes[0]
    if Route.UNSAFE_OR_INJECTION in routes:
        return Route.UNSAFE_OR_INJECTION
    if {Route.ANSWERED, Route.PARTIALLY_ANSWERED} & set(routes):
        return Route.PARTIALLY_ANSWERED
    return min(routes, key=SEVERITY.index)


def unique_citations(outcomes: list[PartOutcome]) -> list[Citation]:
    seen: dict[str, Citation] = {}
    for outcome in outcomes:
        for citation in outcome.citations:
            seen.setdefault(citation.url, citation)
    return list(seen.values())


def unique_pages(pages: list[RelatedPage]) -> list[RelatedPage]:
    unique: dict[str, RelatedPage] = {}
    for page in pages:
        unique.setdefault(page.url, page)
    return list(unique.values())


def marker_ids(text: str) -> list[str]:
    """Ids inside bracket markers such as `[c2]` or `[c1, c3]`, outside code, in order."""
    ids = []
    for match in _MARKER.finditer(_CODE.sub("", text)):
        ids.extend(i.strip() for i in match.group(1).split(","))
    return ids


def citations_for(draft: AnswerDraft, snapshot: Snapshot, ledger: dict) -> list[Citation]:
    """Unique citations in first-use order, titled from the page actually read."""
    seen, citations = set(), []
    for cited in draft.citations:
        base, anchor = split_anchor(cited.url)
        url = f"{base}#{anchor}" if anchor else base
        if url in seen:
            continue
        seen.add(url)
        page = ledger.get(base) or snapshot.page(base)
        heading = None
        if page and anchor and (index := page.find_section(anchor)) is not None:
            heading = page.sections[index].heading
        citations.append(Citation(title=page.title if page else base, url=url, heading=heading))
    return citations


def related_pages_for(draft: AnswerDraft, snapshot: Snapshot) -> list[RelatedPage]:
    # Only pages the index knows about; the model's titles are replaced with the real ones.
    pages = []
    for related in draft.related_pages:
        base, _ = split_anchor(related.url)
        entry = snapshot.entry(base)
        page = snapshot.page(base)
        if entry or page:
            pages.append(RelatedPage(title=(entry or page).title, url=base))
    return pages


def number_markers(draft: AnswerDraft, citations: list[Citation], text: str | None = None) -> str:
    """Replace inline citation ids such as `[c2]` or `[c1, c3]` with numbered source links, in
    the draft's answer or in `text`."""
    position = {c.url: n for n, c in enumerate(citations, start=1)}
    by_id = {}
    for cited in draft.citations:
        base, anchor = split_anchor(cited.url)
        url = f"{base}#{anchor}" if anchor else base
        by_id[cited.id] = (position[url], url)

    def replace(match: re.Match) -> str:
        ids = [i.strip() for i in match.group(1).split(",")]
        if not all(i in by_id for i in ids):
            return match.group(0)
        return "".join(f"[\\[{by_id[i][0]}\\]]({by_id[i][1]})" for i in dict.fromkeys(ids))

    return _MARKER.sub(replace, draft.answer_md if text is None else text)


def cited_urls(draft: AnswerDraft, ids: list[str]) -> list[str]:
    by_id = {c.id: c.url for c in draft.citations}
    return [canonical(by_id[i]) for i in ids if i in by_id]


def canonical(url: str) -> str:
    base, anchor = split_anchor(url)
    return f"{base}#{anchor}" if anchor else base


def render(
    outcomes: list[PartOutcome],
    citations: list[Citation],
    related: list[RelatedPage],
    *,
    language: str = "en",
    next_steps: Sequence[NextStep] = (),
    notes: Sequence[str] = (),
    docs_as_of: datetime | None = None,
    stale: bool = False,
) -> str:
    """The reply markdown. Several parts get one section each; sources are numbered across
    the whole turn and listed once. Ends with when the docs were fetched."""

    def label(key: str) -> str:
        return terminals.text(key, language)

    blocks = [f"_{note}_" for note in notes]
    for outcome in outcomes:
        if len(outcomes) > 1:
            blocks.append(f"### {outcome.question}")
        blocks += _part_blocks(outcome, citations, language)
    if citations:
        blocks.append(f"**{label('sources')}**\n" + "\n".join(f"- {_link(c)}" for c in citations))
    if related:
        blocks.append(f"**{label('related')}**\n" + related_list(related))
    if next_steps:
        blocks.append(f"{label('not_documented_help')}\n{terminals.links(list(next_steps))}")
    if docs_as_of is not None:
        blocks.append(footer(docs_as_of, stale, language))
    return "\n\n".join(b for b in blocks if b)


def footer(docs_as_of: datetime, stale: bool, language: str) -> str:
    time = docs_as_of.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"_{terminals.text('docs_stale' if stale else 'docs_as_of', language, time=time)}_"


def _part_blocks(outcome: PartOutcome, citations: list[Citation], language: str) -> list[str]:
    draft = outcome.draft
    if draft is None:
        return [outcome.text]
    if draft.route == "needs_clarification" and draft.clarification:
        return [render_clarification(draft.clarification, language)]
    blocks = []
    if draft.premise_correction:
        correction = terminals.text("correction", language)
        blocks.append(f"> **{correction}** {draft.premise_correction.strip()}")
    blocks.append(number_markers(draft, citations).strip())
    for page in outcome.adapted:
        link = f"[{page.title}]({page.url})"
        blocks.append(f"_{terminals.text('adapted', language, link=link)}_")
    for conflict in draft.conflicts:
        sources = number_markers(draft, citations, f"[{', '.join(conflict.citation_ids)}]")
        heads_up = terminals.text("heads_up", language)
        blocks.append(f"> **{heads_up}** {conflict.summary.strip()} {sources}")
    if draft.undocumented:
        gaps = "\n".join(f"- {u}" for u in draft.undocumented)
        blocks.append(f"**{terminals.text('not_covered', language)}**\n{gaps}")
    return blocks


def render_clarification(clarification: Clarification, language: str) -> str:
    options = "\n".join(f"{n}. {o}" for n, o in enumerate(clarification.options, start=1))
    hint = terminals.text("clarify_hint", language)
    return f"{clarification.question.strip()}\n\n{options}\n\n_{hint}_"


def related_list(related: list[RelatedPage]) -> str:
    return "\n".join(f"- [{p.title}]({p.url})" for p in related)


def _link(citation: Citation) -> str:
    label = f"{citation.title} › {citation.heading}" if citation.heading else citation.title
    return f"[{label}]({citation.url})"
