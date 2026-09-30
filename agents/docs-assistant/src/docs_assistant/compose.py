"""Turn an accepted draft into the reply text and the typed citation list."""

from __future__ import annotations

import re

from docs_assistant.corpus.cache import Snapshot
from docs_assistant.corpus.parser import split_anchor
from docs_assistant.schemas import AnswerDraft, Citation, RelatedPage

_MARKER = re.compile(r"\[([\w-]+(?:\s*,\s*[\w-]+)*)\](?!\()")


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


def number_markers(draft: AnswerDraft, citations: list[Citation]) -> str:
    """Replace inline citation ids such as `[c2]` or `[c1, c3]` with numbered source links."""
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

    return _MARKER.sub(replace, draft.answer_md)


def render(draft: AnswerDraft, citations: list[Citation], related: list[RelatedPage]) -> str:
    parts = [number_markers(draft, citations).strip()]
    if draft.premise_correction:
        parts.insert(0, f"> **Correction:** {draft.premise_correction.strip()}")
    if draft.undocumented:
        parts.append(
            "**Not covered in the docs:**\n" + "\n".join(f"- {u}" for u in draft.undocumented)
        )
    if citations:
        parts.append("**Sources**\n" + "\n".join(f"- {_link(c)}" for c in citations))
    if related:
        parts.append("**Related pages**\n" + "\n".join(f"- [{p.title}]({p.url})" for p in related))
    return "\n\n".join(p for p in parts if p)


def _link(citation: Citation) -> str:
    label = f"{citation.title} › {citation.heading}" if citation.heading else citation.title
    return f"[{label}]({citation.url})"
