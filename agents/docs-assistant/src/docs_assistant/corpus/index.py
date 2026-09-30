"""BM25 search over heading-level sections.

Exact API names decide most docs questions (`MultiTurnMetric`, `RHESIS_BASE_URL`, `@endpoint`), so
lexical search is the right first tool for a ~300-page corpus; see docs/architecture.md.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from docs_assistant.corpus.parser import IndexEntry, Page

_WORD = re.compile(r"[A-Za-z0-9_]+")
_HYPHENATED = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_STOPWORDS = frozenset(
    "a an and are as at be by can do does for from how i in is it my of on or the this to "
    "what when where which with you your".split()
)
TITLE_BOOST = 3
HEADING_BOOST = 2
DESCRIPTION_BOOST = 2
# Contributor docs are for people working on Rhesis itself; rank them below user docs.
CONTRIBUTE_WEIGHT = 0.6
SNIPPET_CHARS = 300


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens. `MultiTurnMetric` and `max_turns` also yield their parts, and
    hyphenated terms like `Single-Turn` also yield `singleturn`, so they outrank plain `turn`."""
    tokens = [m.group(0).replace("-", "").lower() for m in _HYPHENATED.finditer(text)]
    for word in _WORD.findall(text):
        token = word.lower()
        if token in _STOPWORDS or len(token) < 2:
            continue
        tokens.append(token)
        parts = [p.lower() for p in _CAMEL.sub("_", word).split("_") if len(p) > 1]
        if len(parts) > 1:
            tokens.extend(p for p in parts if p not in _STOPWORDS)
    return tokens


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str
    anchor: str
    heading: str
    snippet: str
    score: float
    section: str


@dataclass
class _Doc:
    url: str
    title: str
    anchor: str
    heading: str
    text: str
    section: str
    terms: Counter
    length: int


class SearchIndex:
    def __init__(self, pages: list[Page], entries: list[IndexEntry], k1=1.5, b=0.75) -> None:
        self.k1, self.b = k1, b
        descriptions = {e.url: e.description for e in entries}
        self._docs = [self._section_doc(p, s, descriptions) for p in pages for s in p.sections]
        page_urls = {p.url for p in pages}
        # Glossary terms that exist only in the index (no MDX page) are searchable by description.
        self._docs += [self._entry_doc(e) for e in entries if e.url not in page_urls]
        self._df: Counter = Counter()
        for doc in self._docs:
            self._df.update(doc.terms.keys())
        self._avg_len = sum(d.length for d in self._docs) / max(len(self._docs), 1)

    def __len__(self) -> int:
        return len(self._docs)

    def search(self, query: str, *, section: str | None = None, k: int = 6) -> list[SearchHit]:
        terms = tokenize(query)
        if not terms:
            return []
        boost_contribute = section == "contribute" or "contribut" in query.lower()
        scored = []
        for doc in self._docs:
            if section and doc.section != section:
                continue
            score = self._score(doc, terms)
            if score <= 0:
                continue
            if doc.section == "contribute" and not boost_contribute:
                score *= CONTRIBUTE_WEIGHT
            scored.append((score, doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [self._hit(doc, score, terms) for score, doc in _one_per_section(scored)[:k]]

    def _score(self, doc: _Doc, terms: list[str]) -> float:
        n = len(self._docs)
        score = 0.0
        for term in set(terms):
            tf = doc.terms.get(term, 0)
            if not tf:
                continue
            df = self._df[term]
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            norm = tf + self.k1 * (1 - self.b + self.b * doc.length / self._avg_len)
            score += idf * tf * (self.k1 + 1) / norm
        return score

    @staticmethod
    def _section_doc(page: Page, section, descriptions: dict[str, str]) -> _Doc:
        description = descriptions.get(page.url, "") if not section.anchor else ""
        terms = Counter(tokenize(section.text))
        for token in tokenize(page.title):
            terms[token] += TITLE_BOOST
        for token in tokenize(section.heading):
            terms[token] += HEADING_BOOST
        for token in tokenize(description):
            terms[token] += DESCRIPTION_BOOST
        if not section.anchor:
            # The intro stands for the whole page: a question spanning several sections
            # ("single-turn vs multi-turn") should still find the page that covers both.
            for token in tokenize(" ".join(s.heading for s in page.sections if s.anchor)):
                terms[token] += 1
        return _Doc(
            url=page.url,
            title=page.title,
            anchor=section.anchor,
            heading=section.heading,
            text=section.text,
            section=page.section,
            terms=terms,
            length=sum(terms.values()),
        )

    @staticmethod
    def _entry_doc(entry: IndexEntry) -> _Doc:
        terms = Counter(tokenize(entry.description))
        for token in tokenize(entry.title):
            terms[token] += TITLE_BOOST
        return _Doc(
            url=entry.url,
            title=entry.title,
            anchor="",
            heading=entry.title,
            text=entry.description,
            section=entry.section,
            terms=terms,
            length=sum(terms.values()),
        )

    @staticmethod
    def _hit(doc: _Doc, score: float, terms: list[str]) -> SearchHit:
        return SearchHit(
            url=doc.url,
            title=doc.title,
            anchor=doc.anchor,
            heading=doc.heading,
            snippet=_snippet(doc.text, terms),
            score=round(score, 3),
            section=doc.section,
        )


def _one_per_section(scored: list[tuple[float, _Doc]]) -> list[tuple[float, _Doc]]:
    seen, unique = set(), []
    for score, doc in scored:
        key = (doc.url, doc.anchor)
        if key not in seen:
            seen.add(key)
            unique.append((score, doc))
    return unique


def _snippet(text: str, terms: list[str]) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    lowered = flat.lower()
    positions = [lowered.find(t) for t in terms if lowered.find(t) >= 0]
    start = max(min(positions) - 80, 0) if positions else 0
    snippet = flat[start : start + SNIPPET_CHARS]
    return ("…" if start else "") + snippet + ("…" if start + SNIPPET_CHARS < len(flat) else "")
