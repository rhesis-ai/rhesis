"""Deterministic checks on an answer draft, run before anything reaches the user.

Rules (numbering follows docs/architecture.md):
1. every citation URL is a page read this turn (search snippets don't count);
2. a citation anchor is one of that page's headings;
3. a citation quote is at least 20 characters and appears on that page word for word, after
   normalizing whitespace and markdown;
4. every claim cites at least one citation, and every cited id exists, in the claims and in the
   `[c1]` markers of answer_md;
5. the route matches the shape of the draft, and a clarifying question is only allowed when the
   conversation hasn't just had one;
6. every fenced code block in answer_md is copied from a page read this turn, or is listed in
   adapted_code with the page it was adapted from;
7. every link in answer_md is a known docs page, or appears on a page read this turn;
8. related_pages are pages the docs index knows.

When a draft keeps failing, `salvage` keeps only the claims whose citations pass rules 1-3.
"""

from __future__ import annotations

import re

from docs_assistant.compose import marker_ids
from docs_assistant.corpus.cache import Snapshot
from docs_assistant.corpus.parser import Page, canonical_url, split_anchor
from docs_assistant.schemas import AnswerDraft, DraftClaim

# What a citation id looks like ("c1"); other bracketed words in prose are not markers.
_ID_LIKE = re.compile(r"^[A-Za-z]{1,3}\d+$")
_FENCED = re.compile(r"^\s*(```|~~~)[^\n]*\n(.*?)^\s*\1", re.DOTALL | re.MULTILINE)
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_MD_LINK_TEXT = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_MARKS = re.compile(r"[*_`>#|]+")
_SPACE = re.compile(r"\s+")
_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})

MIN_OPTIONS, MAX_OPTIONS = 2, 4
MIN_QUOTE_CHARS = 20


def validate(
    draft: AnswerDraft,
    ledger: dict[str, Page],
    snapshot: Snapshot | None = None,
    *,
    allow_clarify: bool = True,
) -> list[str]:
    """Return the problems with a draft; an empty list means it may be shown."""
    if draft.route == "needs_clarification" and not allow_clarify:
        return [
            "you may not ask a clarifying question now; answer the likely readings briefly, "
            "each with its own citations"
        ]
    return [
        *[p for citation in draft.citations for p in _citation_problems(citation, ledger)],
        *_check_claims(draft),
        *_check_markers(draft),
        *_check_code(draft, ledger),
        *_check_links(draft, ledger, snapshot),
        *_check_related(draft, snapshot),
        *_check_route(draft),
    ]


def normalize(text: str) -> str:
    """Text as compared for quotes: no markdown marks or link targets, one space, any case."""
    text = _MD_LINK_TEXT.sub(lambda m: m.group(1), text.translate(_QUOTES))
    return _SPACE.sub(" ", _MD_MARKS.sub(" ", text)).strip().casefold()


def _citation_problems(citation, ledger: dict[str, Page]) -> list[str]:
    url, anchor = split_anchor(citation.url)
    page = ledger.get(url)
    if page is None:
        return [
            f"citation {citation.id}: {citation.url} was not read this turn; "
            "call fetch_page on it first or remove the citation"
        ]
    problems = []
    if anchor and anchor not in page.anchors:
        problems.append(
            f"citation {citation.id}: #{anchor} is not a heading on {url}; use an anchor from "
            "the headings fetch_page listed, or cite the page without one"
        )
    quote = citation.quote.strip()
    if len(quote) < MIN_QUOTE_CHARS:
        problems.append(
            f"citation {citation.id}: the quote must be at least {MIN_QUOTE_CHARS} characters "
            "copied from the page"
        )
    elif normalize(quote) not in normalize(page.body):
        problems.append(
            f"citation {citation.id}: the quote is not on {url} word for word; copy the exact "
            "sentence from the page"
        )
    return problems


def _check_code(draft: AnswerDraft, ledger: dict[str, Page]) -> list[str]:
    def squash(code: str) -> str:
        return _SPACE.sub(" ", code).strip()

    docs_code = [squash(block) for page in ledger.values() for block in page.code_blocks]
    adapted = [squash(a.code) for a in draft.adapted_code if canonical_url(a.source_url) in ledger]
    problems = []
    for n, match in enumerate(_FENCED.finditer(draft.answer_md), start=1):
        code = squash(match.group(2))
        if not code or any(code in block for block in docs_code):
            continue
        if not any(code in a or a in code for a in adapted if a):
            problems.append(
                f"code block {n} in answer_md is not copied from a page you read; copy it "
                "exactly, or list it in adapted_code with the source_url of the page you "
                "adapted it from"
            )
    return problems


def _check_links(
    draft: AnswerDraft, ledger: dict[str, Page], snapshot: Snapshot | None
) -> list[str]:
    bodies = [page.body for page in ledger.values()]
    problems = []
    for href in dict.fromkeys(_LINK.findall(draft.answer_md)):
        if href.startswith("#"):
            continue
        if href.startswith("/") or "docs.rhesis.ai" in href:
            url = canonical_url(href)
            if url in ledger or (snapshot is not None and snapshot.known_url(url)):
                continue
            problems.append(f"link {href} is not a docs page; link only pages that exist")
        elif not any(href in body for body in bodies):
            problems.append(f"link {href} does not appear on any page you read; remove it")
    return problems


def _check_related(draft: AnswerDraft, snapshot: Snapshot | None) -> list[str]:
    if snapshot is None:
        return []
    return [
        f"related page {page.url} is not in the docs index; pick pages from search or list_sections"
        for page in draft.related_pages
        if not snapshot.known_url(page.url)
    ]


def salvage(
    draft: AnswerDraft, ledger: dict[str, Page], snapshot: Snapshot | None = None
) -> AnswerDraft | None:
    """The claims whose every citation passes rules 1-3, as a partial answer; None if none do
    or the result still fails."""
    by_id = {c.id: c for c in draft.citations}

    def grounded(claim: DraftClaim) -> bool:
        cited = [by_id.get(i) for i in claim.citation_ids]
        return bool(cited) and all(c and not _citation_problems(c, ledger) for c in cited)

    keep = {n for n, claim in enumerate(draft.claims) if grounded(claim)}
    kept = drop_claims(draft, keep)
    if kept is None or validate(kept, ledger, snapshot):
        return None
    return kept


def drop_claims(draft: AnswerDraft, keep: set[int]) -> AnswerDraft | None:
    """The draft cut down to the claims in `keep`, as partially_answered; None if none remain.

    The model's prose may mix kept and dropped claims, so the answer is rebuilt from the kept
    claims alone, each with its citation markers. The dropped ones move to undocumented.
    """
    kept = [c for n, c in enumerate(draft.claims) if n in keep]
    if not kept:
        return None
    ids = {i for claim in kept for i in claim.citation_ids}
    lines = [f"- {c.text.strip()} " + "".join(f"[{i}]" for i in c.citation_ids) for c in kept]
    dropped = [c.text.strip() for n, c in enumerate(draft.claims) if n not in keep]
    return draft.model_copy(
        update={
            "route": "partially_answered",
            "answer_md": "\n".join(lines),
            "claims": kept,
            "citations": [c for c in draft.citations if c.id in ids],
            "conflicts": [c for c in draft.conflicts if set(c.citation_ids) <= ids],
            "undocumented": [*draft.undocumented, *dropped] or ["Parts of the original answer"],
            "premise_correction": None,
            "clarification": None,
            "adapted_code": [],
        }
    )


def _check_claims(draft: AnswerDraft) -> list[str]:
    ids = [c.id for c in draft.citations]
    problems = [
        f"citation id {i} is used twice" for i in sorted({i for i in ids if ids.count(i) > 1})
    ]
    known = set(ids)
    for n, claim in enumerate(draft.claims, start=1):
        if not claim.citation_ids:
            problems.append(f"claim {n} has no citation")
        for missing in [i for i in claim.citation_ids if i not in known]:
            problems.append(f"claim {n} cites {missing}, which is not in citations")
    for n, conflict in enumerate(draft.conflicts, start=1):
        if len(set(conflict.citation_ids)) < 2:
            problems.append(f"conflict {n} must cite the pages on both sides (two citations)")
        for missing in [i for i in conflict.citation_ids if i not in known]:
            problems.append(f"conflict {n} cites {missing}, which is not in citations")
    return problems


def _check_markers(draft: AnswerDraft) -> list[str]:
    # An unknown marker would reach the user as a stray "[c9]" with no source behind it.
    known = {c.id for c in draft.citations}
    unknown = [i for i in marker_ids(draft.answer_md) if _ID_LIKE.match(i) and i not in known]
    return [
        f"answer_md uses [{i}], which is not in citations; add that citation or remove the marker"
        for i in dict.fromkeys(unknown)
    ]


def _check_route(draft: AnswerDraft) -> list[str]:
    has_citations, has_gaps = bool(draft.citations), bool(draft.undocumented)
    match draft.route:
        case "answered":
            problems = (
                [] if has_citations and draft.claims else ["answered needs claims with citations"]
            )
            if has_gaps:
                problems.append(
                    "answered must have an empty undocumented list; use partially_answered"
                )
            return problems
        case "partially_answered":
            problems = [] if has_citations else ["partially_answered needs at least one citation"]
            if not has_gaps:
                problems.append("partially_answered must list what the docs don't cover")
            return problems
        case "not_documented":
            if draft.claims or draft.citations:
                return ["not_documented must not make claims or cite pages; use related_pages"]
            return []
        case "false_premise":
            problems = (
                []
                if (draft.premise_correction or "").strip()
                else ["false_premise needs premise_correction"]
            )
            if not has_citations:
                problems.append("false_premise needs a citation showing the premise is wrong")
            return problems
        case "needs_clarification":
            return _check_clarification(draft)
    return [f"unknown route {draft.route}"]


def _check_clarification(draft: AnswerDraft) -> list[str]:
    problems = []
    clarification = draft.clarification
    if clarification is None or not clarification.question.strip():
        return ["needs_clarification needs a clarification with a question and options"]
    options = [o for o in clarification.options if o.strip()]
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        problems.append(f"needs_clarification needs {MIN_OPTIONS} to {MAX_OPTIONS} options")
    if draft.claims or draft.citations:
        problems.append("needs_clarification must not make claims or cite pages")
    return problems
