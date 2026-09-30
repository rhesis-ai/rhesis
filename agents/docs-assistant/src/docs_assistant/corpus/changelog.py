"""Read the changelog page's Keep-a-Changelog `## [x.y.z] - YYYY-MM-DD` blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from docs_assistant.corpus.index import tokenize
from docs_assistant.corpus.parser import Page

# Words every release note would match, so they can't narrow anything down.
_CHANGELOG_FILLER = frozenset(
    "new what whats changed change changes release released releases version versions latest "
    "since not there any".split()
)
_VERSION_HEADING = re.compile(
    r"^\[(?P<version>[^\]]+)\](?:\s*-\s*(?P<date>\d{4}-\d{2}-\d{2}))?", re.IGNORECASE
)


@dataclass(frozen=True)
class ChangelogEntry:
    version: str
    date: str | None
    anchor: str
    body: str


def parse_changelog(page: Page) -> list[ChangelogEntry]:
    entries = []
    for section in page.sections:
        if section.level != 2:
            continue
        match = _VERSION_HEADING.match(section.heading)
        if match:
            entries.append(
                ChangelogEntry(
                    version=match.group("version"),
                    date=match.group("date"),
                    anchor=section.anchor,
                    body=_version_body(page, section.anchor),
                )
            )
    return entries


def _version_body(page: Page, anchor: str) -> str:
    # A version's `### Added` / `### Fixed` subsections are their own sections; fold them back in.
    start = page.find_section(anchor)
    parts = [page.sections[start].text]
    for section in page.sections[start + 1 :]:
        if section.level <= 2:
            break
        parts.append(section.text)
    return "\n\n".join(parts)


def _version_key(version: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", version)
    return tuple(int(n) for n in numbers) if numbers else (10**6,)


def select_entries(
    entries: list[ChangelogEntry],
    *,
    version: str | None = None,
    since: str | None = None,
    query: str | None = None,
    limit: int = 5,
) -> list[ChangelogEntry]:
    """Filter changelog entries. With no filters, the latest releases come first."""
    selected = [e for e in entries if e.version.lower() != "unreleased"] or entries
    if version:
        wanted = version.strip().lstrip("vV")
        selected = [e for e in entries if e.version == wanted]
    if since:
        floor = _version_key(since)
        selected = [e for e in selected if _version_key(e.version) > floor]
    words = [w for w in tokenize(query or "") if w not in _CHANGELOG_FILLER]
    if words:
        selected = [e for e in selected if any(w in e.body.lower() for w in words)]
    return selected[:limit]
