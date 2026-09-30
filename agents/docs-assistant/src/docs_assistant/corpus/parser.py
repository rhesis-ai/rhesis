"""Parse the docs site's LLM views into pages, sections, anchors, code blocks and links.

Inputs are `/llms.txt` (the index: title, URL, description, section per page) and
`/llms-full.txt` (every page's cleaned markdown, each behind a `url`/`title` frontmatter block).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from docs_assistant.config import PUBLIC_DOCS_URL

_FRONTMATTER = re.compile(r"^---\nurl: (?P<url>\S+)\ntitle: (?P<title>.*)\n---\n", re.MULTILINE)
_HEADING = re.compile(r"^(?P<hashes>#{1,3}) +(?P<text>.+?) *#*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_MD_LINK = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<href>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
_INDEX_ENTRY = re.compile(r"^- \[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\)(?::\s*(?P<desc>.*))?$")
_SLUG_DROP = re.compile(r"[^\w\- ]", re.UNICODE)

# Top-level URL segment → the section name the tools and triage use.
SECTION_BY_SEGMENT = {
    "docs": "docs",
    "sdk": "sdk",
    "guides": "guides",
    "self-hosting": "self_hosting",
    "glossary": "glossary",
    "changelog": "changelog",
    "contribute": "contribute",
}


@dataclass(frozen=True)
class IndexEntry:
    title: str
    url: str
    description: str
    section: str


@dataclass(frozen=True)
class Link:
    text: str
    url: str


@dataclass
class Section:
    anchor: str
    heading: str
    level: int
    text: str


@dataclass
class Page:
    url: str
    path: str
    title: str
    body: str
    sections: list[Section] = field(default_factory=list)
    code_blocks: list[str] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)

    @property
    def section(self) -> str:
        return section_for_path(self.path)

    @property
    def anchors(self) -> set[str]:
        return {s.anchor for s in self.sections if s.anchor}

    def find_section(self, anchor: str) -> int | None:
        for i, s in enumerate(self.sections):
            if s.anchor == anchor:
                return i
        return None


def section_for_path(path: str) -> str:
    return SECTION_BY_SEGMENT.get(path.split("/", 1)[0], "docs")


def canonical_url(url_or_path: str) -> str:
    """Normalise any docs URL form to `https://docs.rhesis.ai/<path>` without anchor or `.md`.

    Accepts absolute URLs on any host (mirrors included), site-relative paths, `.md` links and
    `/api/md/` links. The anchor is dropped; use `split_anchor` to keep it.
    """
    return f"{PUBLIC_DOCS_URL}/{url_to_path(url_or_path)}".rstrip("/")


def url_to_path(url_or_path: str) -> str:
    value = url_or_path.strip().split("#", 1)[0].split("?", 1)[0]
    value = re.sub(r"^https?://[^/]+", "", value)
    value = value.removeprefix("/api/md").strip("/")
    return value.removesuffix(".md").strip("/")


def split_anchor(url: str) -> tuple[str, str | None]:
    base, _, anchor = url.partition("#")
    return canonical_url(base), (anchor or None)


def slugify(heading: str) -> str:
    """GitHub-style heading slug, matching the ids Nextra puts on the HTML site."""
    text = _MD_LINK.sub(lambda m: m.group("text"), heading)
    text = _SLUG_DROP.sub("", text.lower())
    return text.replace(" ", "-")


def parse_llms_txt(text: str) -> list[IndexEntry]:
    """Read the index. Only docs.rhesis.ai links become entries; the section follows the URL."""
    entries: dict[str, IndexEntry] = {}
    for line in text.splitlines():
        match = _INDEX_ENTRY.match(line.strip())
        if not match or not _is_docs_url(match.group("url")):
            continue
        url = canonical_url(match.group("url"))
        if url in entries:
            continue
        entries[url] = IndexEntry(
            title=match.group("title").strip(),
            url=url,
            description=(match.group("desc") or "").strip(),
            section=section_for_path(url_to_path(url)),
        )
    return list(entries.values())


def parse_llms_full(text: str) -> list[Page]:
    matches = list(_FRONTMATTER.finditer(text))
    pages = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pages.append(build_page(match.group("url"), match.group("title"), text[match.end() : end]))
    return pages


def parse_page_markdown(text: str) -> Page | None:
    """Parse one `/api/md/<path>` response, which carries the same frontmatter block."""
    pages = parse_llms_full(text)
    return pages[0] if pages else None


def build_page(url: str, title: str, body: str) -> Page:
    url = canonical_url(url)
    body = body.strip("\n")
    page = Page(url=url, path=url_to_path(url), title=title.strip(), body=body)
    page.sections = _split_sections(page.title, body)
    page.code_blocks = _code_blocks(body)
    page.links = _links(body)
    return page


def _split_sections(title: str, body: str) -> list[Section]:
    sections: list[Section] = []
    seen: dict[str, int] = {}
    heading, anchor, level, lines = title, "", 1, []
    in_fence = False
    for line in body.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        match = None if in_fence else _HEADING.match(line)
        if match and len(match.group("hashes")) > 1:
            sections.append(Section(anchor, heading, level, "\n".join(lines).strip()))
            heading = match.group("text").strip()
            level = len(match.group("hashes"))
            anchor = _unique(slugify(heading), seen)
            lines = [line]
            continue
        lines.append(line)
    sections.append(Section(anchor, heading, level, "\n".join(lines).strip()))
    return [s for s in sections if s.text or s.anchor]


def _unique(slug: str, seen: dict[str, int]) -> str:
    # github-slugger appends -1, -2 … to repeated headings.
    count = seen.get(slug, 0)
    seen[slug] = count + 1
    return slug if count == 0 else f"{slug}-{count}"


def _code_blocks(body: str) -> list[str]:
    blocks, current, fence = [], [], None
    for line in body.splitlines():
        match = _FENCE.match(line)
        if match and fence is None:
            fence, current = match.group(1), []
        elif match and line.strip().startswith(fence):
            blocks.append("\n".join(current))
            fence = None
        elif fence is not None:
            current.append(line)
    return blocks


def _links(body: str) -> list[Link]:
    links, seen = [], set()
    for match in _MD_LINK.finditer(body):
        href = match.group("href")
        if not (href.startswith("/") or _is_docs_url(href)) or href.startswith("//"):
            continue
        base, anchor = split_anchor(href)
        url = f"{base}#{anchor}" if anchor else base
        if url not in seen:
            seen.add(url)
            links.append(Link(text=match.group("text"), url=url))
    return links


def _is_docs_url(url: str) -> bool:
    return url.startswith(PUBLIC_DOCS_URL)
