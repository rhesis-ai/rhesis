"""OWASP Top 10 report extractor.

Downloads any OWASP Top 10 PDF, extracts the full text with heading structure,
and splits it into individual risk sections — usable standalone or as the data
source for the OWASPSynthesizer.

Usage::

    from rhesis.sdk.services.owasp_extractor import fetch_owasp_sections, DEFAULT_OWASP_LLM_PDF_URL

    sections = fetch_owasp_sections(DEFAULT_OWASP_LLM_PDF_URL)
    for section in sections:
        print(section.id, section.name)
        print(section.content[:500])
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Collection, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_OWASP_LLM_PDF_URL = (
    "https://owasp.org/www-project-top-10-for-large-language-model-applications/"
    "assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf"
)
DEFAULT_OWASP_AGENTIC_PDF_URL = "https://genai.owasp.org/download/52117/"

# Reference appendices add noise without attack-surface value.
DEFAULT_SUBSECTION_EXCLUSIONS: frozenset[str] = frozenset(
    {"reference links", "related frameworks and taxonomies", "references"}
)

# Matches "# LLM01:2025 Prompt Injection", "ASI02: Tool Misuse…", etc.
_SECTION_HEADER_RE = re.compile(
    r"^(?:#+ )?([A-Z]{2,5}(?:0[1-9]|10))(?::\d{4})?[\s:\-]+.+",
    re.IGNORECASE,
)

# Words that indicate line 2 of a title is a subsection heading, not a continuation.
_SUBSECTION_KEYWORDS = frozenset(
    {"description", "overview", "references", "mitigations", "prevention", "examples", "impact"}
)

# Bare page numbers: "3", "12", "Page 12".
_PAGE_NUMBER_RE = re.compile(r"^(?:Page\s+)?\d+$", re.IGNORECASE)


@dataclass
class ReportSection:
    """One risk entry extracted from an OWASP Top 10 PDF."""

    id: str  # normalised lowercase, e.g. "llm01"
    name: str  # human-readable, e.g. "Prompt Injection"
    content: str  # full section text with markdown heading markers


def _fetch_pdf_bytes(url: str) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; RhesisSDK/1.0)"}
    response = requests.get(url, timeout=60, headers=headers)
    response.raise_for_status()
    return response.content


def _extract_pdf(pdf_bytes: bytes) -> str:
    """Extract PDF text annotating headings via font-size ratios.

    Two-pass: first find the modal body font size, then emit text with
    "# " / "## " prefixes for sizes ≥ body×1.8 / body×1.3 respectively.
    Pages are separated by form-feed characters for downstream splitting.
    """
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar, LTTextBox, LTTextLine

    all_pages = list(extract_pages(io.BytesIO(pdf_bytes)))

    # First pass: find modal body font size via character frequency.
    size_counter = Counter(
        round(char.size, 1)
        for page_layout in all_pages
        for element in page_layout
        if isinstance(element, LTTextBox)
        for line in element
        if isinstance(line, LTTextLine)
        for char in line
        if isinstance(char, LTChar) and char.size > 5
    )
    if not size_counter:
        raise ValueError("No text found in PDF")

    body_size = size_counter.most_common(1)[0][0]
    h1_threshold = body_size * 1.8
    h2_threshold = body_size * 1.3

    # Second pass: extract text with heading prefixes.
    pages_text: list[str] = []
    for page_layout in all_pages:
        page_blocks: list[str] = []
        for element in sorted(page_layout, key=lambda e: (-e.y1, e.x0)):
            if not isinstance(element, LTTextBox):
                continue
            raw = element.get_text().strip()
            if not raw:
                continue

            char_sizes = [
                char.size
                for line in element
                if isinstance(line, LTTextLine)
                for char in line
                if isinstance(char, LTChar) and char.size > 5
            ]
            # Normalise kerning spaces and strip trailing whitespace per line.
            text = "\n".join(line.rstrip() for line in re.sub(r"[ \t]{2,}", " ", raw).split("\n"))
            # Split at sentence boundaries within a text box so each sentence
            # becomes its own block — prevents adjacent paragraphs from merging.
            text = re.sub(r"([.!?])\n([A-Z])", r"\1\n\n\2", text)
            if char_sizes:
                max_size = max(char_sizes)
                if max_size >= h1_threshold:
                    text = "# " + text
                elif max_size >= h2_threshold:
                    text = "## " + text
            page_blocks.append(text)

        pages_text.append("\n\n".join(page_blocks))

    return "\x0c".join(pages_text)


def _extract_name(lines: list[str], raw_id: str) -> str:
    """Extract the section name, handling titles that wrap across two lines."""
    first = re.sub(r"^#+\s*", "", lines[0]) if lines else ""
    name = re.sub(
        rf"^{re.escape(raw_id)}(?::\d{{4}})?[\s:\-]+",
        "",
        first,
        flags=re.IGNORECASE,
    ).strip()

    if len(lines) > 1:
        second = re.sub(r"^#+\s*", "", lines[1])
        if (
            second
            and second.lower() not in _SUBSECTION_KEYWORDS
            and not re.match(r"^[A-Z]{2,5}(?:0[1-9]|10)", second)
        ):
            name = name + " " + second

    return name


def _detect_boilerplate(
    pages: list[str],
    header_window: int = 2,
    footer_window: int = 3,
    threshold: float = 0.30,
) -> frozenset[str]:
    """Return strings that recur as running headers/footers across pages.

    Scans the first header_window lines (skipping line 0, which is real content)
    and the last footer_window lines of each page. The 30% threshold captures
    running headers (~35–100%) while staying above content subheadings like
    "Description" (~22%).
    """
    counts: Counter = Counter()
    n = len(pages)

    for page in pages:
        lines = [line.strip() for line in page.split("\n") if line.strip()]
        if not lines:
            continue
        for line in lines[1 : 1 + header_window]:  # line 0 is real content, never boilerplate
            counts[line] += 1
        for line in lines[-footer_window:]:
            counts[line] += 1

    min_count = max(2, int(n * threshold))
    return frozenset(line for line, count in counts.items() if count >= min_count)


def _clean_section(content: str, boilerplate: frozenset[str]) -> str:
    """Strip boilerplate, page numbers, and PDF layout artifacts from section content.

    Processes pages individually to join cross-page sentence breaks precisely:
    pages ending without .!?: are joined with a space; others get a paragraph
    break. Within each page, detached list numbers and mid-sentence text-box
    splits are merged.
    """
    cleaned_pages: list[str] = []

    for page in content.split("\x0c"):
        lines = [
            line
            for line in page.split("\n")
            if line.strip() not in boilerplate and not _PAGE_NUMBER_RE.match(line.strip())
        ]
        page_text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        if not page_text:
            continue

        # Reattach detached "N." list numbers and join mid-sentence text-box splits.
        joined: list[str] = []
        for block in page_text.split("\n\n"):
            if joined:
                prev_last = joined[-1].rstrip().split("\n")[-1].strip()
                block_first = block.lstrip().split("\n")[0].strip()

                # Bare "N." block: in a two-column PDF the list number box can appear
                # *after* its content box in reading order.  If prev ended mid-sentence,
                # this number labels that content → prepend it; otherwise it starts a
                # new item and will be joined forward by the check below.
                if re.match(r"^\d+\.$", block.strip()):
                    if prev_last and prev_last[-1] not in ".!?:" and not prev_last.startswith("#"):
                        # Out-of-order column label: prepend number to preceding content.
                        prefix = block.strip() + " "
                        if not re.match(r"^\d+\.\s", joined[-1].lstrip()):
                            joined[-1] = prefix + joined[-1].lstrip()
                    else:
                        joined.append(block)
                    continue

                # prev block ended with a bare "N." → join next content to it.
                if re.match(r"^\d+\.$", prev_last) and not block_first.startswith("#"):
                    joined[-1] = joined[-1].rstrip() + " " + block.lstrip()
                    continue

                # "N. lowercase" in one text box = sentence continuation with orphaned number.
                list_num_cont = re.match(r"^(\d+\.\s+)[a-z]", block_first)
                if (
                    prev_last
                    and prev_last[-1] not in ".!?:"
                    and not prev_last.startswith("#")
                    and not block_first.startswith("#")
                    and block_first
                    and (block_first[0].islower() or list_num_cont)
                ):
                    if list_num_cont:
                        prefix = list_num_cont.group(1)
                        body = block.lstrip()[len(prefix) :]
                        if not re.match(r"^\d+\.\s", joined[-1].lstrip()):
                            joined[-1] = prefix + joined[-1].lstrip()
                        joined[-1] = joined[-1].rstrip() + " " + body
                    else:
                        joined[-1] = joined[-1].rstrip() + " " + block.lstrip()
                    continue

            joined.append(block)

        cleaned_pages.append("\n\n".join(joined))

    if not cleaned_pages:
        return ""

    result = cleaned_pages[0]
    for page in cleaned_pages[1:]:
        last_line = result.rstrip().split("\n")[-1].strip()
        first_line = page.lstrip().split("\n")[0].strip()

        if re.match(r"^\d+\.$", last_line) and not first_line.startswith("#"):
            result = result.rstrip() + " " + page.lstrip()
        elif last_line.startswith("#") or first_line.startswith("#"):
            result = result.rstrip() + "\n\n" + page.lstrip()
        elif last_line and last_line[-1] not in ".!?:":
            if re.match(r"^\d+\.\s+[a-z]", first_line):
                body = re.sub(r"^\d+\.\s+", "", page.lstrip(), count=1)
                result = result.rstrip() + " " + body
            else:
                result = result.rstrip() + " " + page.lstrip()
        else:
            result = result.rstrip() + "\n\n" + page.lstrip()

    result = re.sub(r"\n{3,}", "\n\n", result).strip()

    # "N." immediately before a heading or at end-of-section — orphaned list number.
    result = re.sub(r"\n\n\d+\.\n\n(?=#)", "\n\n", result)
    result = re.sub(r"\n\n\d+\.\s*$", "", result)
    # "N." injected mid-sentence by PDF column layout between two content lines.
    result = re.sub(r"(?<=[^.!?:])\n\d+\.\n(?=[a-z])", " ", result)

    return result.strip()


def _drop_subsections(content: str, exclusions: Collection[str]) -> str:
    """Remove excluded ## subsections from section content."""
    if not exclusions:
        return content

    bl = frozenset(h.lower().strip() for h in exclusions)
    result: list[str] = []
    skip = False

    for line in content.split("\n"):
        if line.startswith("# "):
            skip = False
            result.append(line)
        elif line.startswith("## "):
            skip = line[3:].strip().lower() in bl
            if not skip:
                result.append(line)
        elif not skip:
            result.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(result)).strip()


def _parse_sections(text: str) -> list[ReportSection]:
    """Split the full PDF text into per-risk ReportSection objects."""
    all_pages = text.split("\x0c")
    boilerplate = _detect_boilerplate(all_pages)
    parts = re.split(r"\x0c(?=(?:#+ )?[A-Z]{2,5}(?:0[1-9]|10)[:\s])", text)

    sections: list[ReportSection] = []
    for part in parts[1:]:  # parts[0] is the preamble
        lines = [line.strip() for line in part.split("\n") if line.strip()]
        if not lines:
            continue
        m = _SECTION_HEADER_RE.match(lines[0])
        if not m:
            continue

        raw_id = m.group(1)
        lines_clean = [line for line in lines if line not in boilerplate]
        sections.append(
            ReportSection(
                id=raw_id.lower(),
                name=_extract_name(lines_clean, raw_id),
                content=_clean_section(part.strip(), boilerplate),
            )
        )

    # Drop appendix pages whose prefix differs from the primary section set.
    if sections:
        prefix = re.match(r"([a-z]+)", sections[0].id).group(1)
        sections = [s for s in sections if s.id.startswith(prefix)]

    return sections


def fetch_owasp_sections(
    url: str,
    subsection_exclusions: Collection[str] = DEFAULT_SUBSECTION_EXCLUSIONS,
    cache_key: Optional[str] = None,
    cache_loader: Optional[Callable[[str], Optional[list[dict]]]] = None,
    cache_writer: Optional[Callable[[str, list[dict]], None]] = None,
) -> list[ReportSection]:
    """Download an OWASP Top 10 PDF and return its risk sections.

    Extracts text with pdfminer (font-size-based heading detection), splits by
    section, and applies the subsection exclusions.  The default exclusions drop
    reference appendices which add noise without attack-surface value.

    Callers can inject ``cache_loader``/``cache_writer`` to skip the expensive
    download + pdfminer parse; this function stays cache-backend agnostic. The
    cache stores un-excluded content, so ``subsection_exclusions`` is applied
    the same way on hit or miss.

    Args:
        url: Direct URL to an OWASP Top 10 PDF.
        subsection_exclusions: Headings to strip from every section, matched
            case-insensitively.  Pass an empty collection to keep all subsections.
        cache_key: Key for the cache callbacks. Defaults to a sha256 of ``url``.
        cache_loader: ``(cache_key) -> [{"id", "name", "content"}, ...] | None``.
            On a hit, the download and parse are skipped.
        cache_writer: ``(cache_key, sections)`` called after a fresh parse to
            persist the content. Not called on a hit.

    Returns:
        Ordered list of :class:`ReportSection` objects.

    Raises:
        requests.HTTPError: If the PDF cannot be downloaded.
        ValueError: If no sections are found in the extracted text.

    Example::

        from rhesis.sdk.services.owasp_extractor import (
            fetch_owasp_sections,
            DEFAULT_OWASP_LLM_PDF_URL,
            DEFAULT_OWASP_AGENTIC_PDF_URL,
        )

        llm_sections = fetch_owasp_sections(DEFAULT_OWASP_LLM_PDF_URL)
        agentic_sections = fetch_owasp_sections(DEFAULT_OWASP_AGENTIC_PDF_URL)
        full_sections = fetch_owasp_sections(DEFAULT_OWASP_LLM_PDF_URL, subsection_exclusions=set())
    """
    key = cache_key or hashlib.sha256(url.encode("utf-8")).hexdigest()

    raw_sections: Optional[list[ReportSection]] = None
    if cache_loader is not None:
        cached = cache_loader(key)
        if cached is not None:
            raw_sections = [
                ReportSection(id=s["id"], name=s["name"], content=s["content"]) for s in cached
            ]
            logger.info(
                "[OWASPExtractor] Loaded %d sections for %r from cache",
                len(raw_sections),
                key,
            )

    if raw_sections is None:
        logger.info("[OWASPExtractor] Fetching report from %s", url)
        pdf_bytes = _fetch_pdf_bytes(url)
        raw_sections = _parse_sections(_extract_pdf(pdf_bytes))

        if not raw_sections:
            raise ValueError(
                f"No top-10 sections found in the PDF at {url}. "
                "The document may not follow the expected OWASP section-per-page layout."
            )

        if cache_writer is not None:
            cache_writer(
                key,
                [{"id": s.id, "name": s.name, "content": s.content} for s in raw_sections],
            )

    sections = raw_sections
    if subsection_exclusions:
        sections = [
            ReportSection(s.id, s.name, _drop_subsections(s.content, subsection_exclusions))
            for s in sections
        ]

    logger.info(
        "[OWASPExtractor] Extracted %d sections: %s", len(sections), [s.id for s in sections]
    )
    return sections
