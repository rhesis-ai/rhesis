"""Deterministic checks on an answer draft, run before anything reaches the user.

Rules checked here (numbering follows docs/architecture.md):
1. every citation URL is a page read this turn;
4. every claim cites at least one citation, and every cited id exists, in the claims and in the
   `[c1]` markers of answer_md;
5. the route matches the shape of the draft.
"""

from __future__ import annotations

import re

from docs_assistant.compose import marker_ids
from docs_assistant.corpus.parser import Page, split_anchor
from docs_assistant.schemas import AnswerDraft

# What a citation id looks like ("c1"); other bracketed words in prose are not markers.
_ID_LIKE = re.compile(r"^[A-Za-z]{1,3}\d+$")


def validate(draft: AnswerDraft, ledger: dict[str, Page]) -> list[str]:
    """Return the problems with a draft; an empty list means it may be shown."""
    return [
        *_check_citation_urls(draft, ledger),
        *_check_claims(draft),
        *_check_markers(draft),
        *_check_route(draft),
    ]


def _check_citation_urls(draft: AnswerDraft, ledger: dict[str, Page]) -> list[str]:
    problems = []
    for citation in draft.citations:
        url, _ = split_anchor(citation.url)
        if url not in ledger:
            problems.append(
                f"citation {citation.id}: {citation.url} was not read this turn; "
                "call fetch_page on it first or remove the citation"
            )
    return problems


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
    return [f"unknown route {draft.route}"]
