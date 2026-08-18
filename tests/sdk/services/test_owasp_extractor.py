"""Tests for rhesis.sdk.services.owasp_extractor.

Covers the fetch_owasp_sections cache hit/miss control flow — including the
empty-cached-list regression from PR #2202 review feedback — plus the pure
text-processing helpers (_extract_name, _drop_subsections, _detect_boilerplate,
_parse_sections), none of which touch the network or pdfminer.
"""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.services.owasp_extractor import (
    ReportSection,
    _detect_boilerplate,
    _drop_subsections,
    _extract_name,
    _parse_sections,
    fetch_owasp_sections,
)

SAMPLE_SECTIONS = [
    ReportSection(
        id="llm01",
        name="Prompt Injection",
        content="# LLM01:2025 Prompt Injection\n\nBody one.",
    ),
    ReportSection(
        id="llm02",
        name="Insecure Output Handling",
        content="# LLM02:2025 Insecure Output Handling\n\nBody two.",
    ),
]


def _as_cache_payload(sections):
    return [{"id": s.id, "name": s.name, "content": s.content} for s in sections]


# ---------------------------------------------------------------------------
# fetch_owasp_sections — cache hit/miss control flow
# ---------------------------------------------------------------------------


class TestFetchOwaspSectionsCaching:
    @patch("rhesis.sdk.services.owasp_extractor._parse_sections")
    @patch("rhesis.sdk.services.owasp_extractor._extract_pdf")
    @patch("rhesis.sdk.services.owasp_extractor._fetch_pdf_bytes")
    def test_cache_hit_skips_download_and_parse(self, mock_fetch, mock_extract, mock_parse):
        loader = MagicMock(return_value=_as_cache_payload(SAMPLE_SECTIONS))
        writer = MagicMock()

        result = fetch_owasp_sections(
            "https://example.com/report.pdf",
            subsection_exclusions=set(),
            cache_loader=loader,
            cache_writer=writer,
        )

        mock_fetch.assert_not_called()
        mock_extract.assert_not_called()
        mock_parse.assert_not_called()
        writer.assert_not_called()
        assert [s.id for s in result] == ["llm01", "llm02"]

    @patch("rhesis.sdk.services.owasp_extractor._parse_sections", return_value=SAMPLE_SECTIONS)
    @patch("rhesis.sdk.services.owasp_extractor._extract_pdf", return_value="fake text")
    @patch("rhesis.sdk.services.owasp_extractor._fetch_pdf_bytes", return_value=b"%PDF-fake")
    def test_cache_miss_downloads_parses_and_writes(self, mock_fetch, mock_extract, mock_parse):
        loader = MagicMock(return_value=None)
        writer = MagicMock()

        result = fetch_owasp_sections(
            "https://example.com/report.pdf",
            subsection_exclusions=set(),
            cache_loader=loader,
            cache_writer=writer,
        )

        mock_fetch.assert_called_once()
        mock_parse.assert_called_once()
        writer.assert_called_once()
        written_key, written_payload = writer.call_args.args
        assert written_payload == _as_cache_payload(SAMPLE_SECTIONS)
        assert [s.id for s in result] == ["llm01", "llm02"]

    @patch("rhesis.sdk.services.owasp_extractor._parse_sections", return_value=SAMPLE_SECTIONS)
    @patch("rhesis.sdk.services.owasp_extractor._extract_pdf", return_value="fake text")
    @patch("rhesis.sdk.services.owasp_extractor._fetch_pdf_bytes", return_value=b"%PDF-fake")
    def test_empty_cached_list_is_treated_as_a_miss_not_valid_data(
        self, mock_fetch, mock_extract, mock_parse
    ):
        """Regression test for PR #2202 review feedback (Harry Cruz).

        A `cache_loader` returning `[]` must not sail past the `raw_sections is
        None` guard as if it were valid cached data — that would skip the
        download, the parse, and the "No top-10 sections found" check, and
        silently return an empty list. It must be treated exactly like a cache
        miss: re-fetch, re-parse, and (since the fresh parse succeeds here)
        repair the cache via cache_writer.
        """
        loader = MagicMock(return_value=[])
        writer = MagicMock()

        result = fetch_owasp_sections(
            "https://example.com/report.pdf",
            subsection_exclusions=set(),
            cache_loader=loader,
            cache_writer=writer,
        )

        mock_fetch.assert_called_once()
        mock_extract.assert_called_once()
        mock_parse.assert_called_once()
        writer.assert_called_once()
        assert result == SAMPLE_SECTIONS
        assert result != []

    @patch("rhesis.sdk.services.owasp_extractor._parse_sections", return_value=[])
    @patch("rhesis.sdk.services.owasp_extractor._extract_pdf", return_value="fake text")
    @patch("rhesis.sdk.services.owasp_extractor._fetch_pdf_bytes", return_value=b"%PDF-fake")
    def test_no_sections_after_fresh_parse_raises(self, mock_fetch, mock_extract, mock_parse):
        """An empty cache is repaired by re-parsing; if the re-parse also finds
        nothing, the no-sections guard must still fire (and never cache the
        empty result)."""
        loader = MagicMock(return_value=[])
        writer = MagicMock()

        with pytest.raises(ValueError, match="No top-10 sections found"):
            fetch_owasp_sections(
                "https://example.com/report.pdf",
                cache_loader=loader,
                cache_writer=writer,
            )

        writer.assert_not_called()

    @patch("rhesis.sdk.services.owasp_extractor._fetch_pdf_bytes")
    def test_subsection_exclusions_applied_to_cached_content(self, mock_fetch):
        """Cache stores un-excluded content; exclusions apply the same on a hit."""
        cached_sections = [
            ReportSection(
                id="llm01",
                name="Prompt Injection",
                content=("# LLM01:2025 Prompt Injection\n\nBody.\n\n## References\n\nDrop me."),
            )
        ]
        loader = MagicMock(return_value=_as_cache_payload(cached_sections))

        result = fetch_owasp_sections("https://example.com/report.pdf", cache_loader=loader)

        mock_fetch.assert_not_called()
        assert "References" not in result[0].content
        assert "Drop me" not in result[0].content
        assert "Body." in result[0].content


# ---------------------------------------------------------------------------
# Pure text-processing helpers
# ---------------------------------------------------------------------------


class TestExtractName:
    def test_single_line_title(self):
        assert _extract_name(["# LLM01:2025 Prompt Injection"], "LLM01") == "Prompt Injection"

    def test_two_line_title_is_merged(self):
        lines = ["# LLM01:2025 Prompt Injection", "## Via Untrusted Content"]
        assert _extract_name(lines, "LLM01") == "Prompt Injection Via Untrusted Content"

    def test_subsection_keyword_on_line_two_is_not_merged(self):
        lines = ["# LLM01:2025 Prompt Injection", "## Description"]
        assert _extract_name(lines, "LLM01") == "Prompt Injection"

    def test_empty_lines_returns_empty_name(self):
        assert _extract_name([], "LLM01") == ""


class TestDropSubsections:
    CONTENT = (
        "# LLM01 Title\n\nIntro text.\n\n"
        "## References\n\nSome reference stuff.\n\n"
        "## Impact\n\nImpact text."
    )

    def test_removes_excluded_subsection(self):
        result = _drop_subsections(self.CONTENT, {"references"})
        assert "References" not in result
        assert "Some reference stuff" not in result
        assert "Impact text." in result

    def test_empty_exclusions_returns_content_unchanged(self):
        assert _drop_subsections(self.CONTENT, set()) == self.CONTENT


class TestDetectBoilerplate:
    def test_flags_recurring_header_and_footer_not_unique_body(self):
        pages = [
            "Title A\nRunning Header\nBody unique A\nPage Footer",
            "Title B\nRunning Header\nBody unique B\nPage Footer",
            "Title C\nRunning Header\nBody unique C\nPage Footer",
        ]

        boilerplate = _detect_boilerplate(pages, header_window=1, footer_window=1)

        assert "Running Header" in boilerplate
        assert "Page Footer" in boilerplate
        assert "Title A" not in boilerplate  # line 0 is never boilerplate
        assert "Body unique A" not in boilerplate


class TestParseSections:
    def test_splits_by_risk_id_and_drops_mismatched_prefix(self):
        # Each page needs >= 6 lines so _detect_boilerplate's header (lines
        # 1-2) and footer (last 3) windows don't overlap within a single
        # page — with shorter pages, a single unique line gets counted twice
        # (once per window) and is misflagged as boilerplate. Subsection
        # keywords ("Overview" / "Impact") also differ per section so they
        # don't collide across pages either.
        text = (
            "OWASP Top 10 for LLM Applications\nIntroduction text.\nMore intro.\n"
            "Even more intro.\nAnd more.\nLast intro line."
            "\x0c# LLM01:2025 Prompt Injection\n\n## Overview\n\n"
            "Body text for one line A.\nBody text for one line B.\n"
            "Body text for one line C.\nBody text for one line D."
            "\x0c# LLM02:2025 Insecure Output Handling\n\n## Impact\n\n"
            "Body text for two line A.\nBody text for two line B.\n"
            "Body text for two line C.\nBody text for two line D."
            "\x0c# APP01:2025 Appendix Risk\n\nShould be dropped entirely.\n"
            "Filler one.\nFiller two.\nFiller three."
        )

        sections = _parse_sections(text)

        assert [s.id for s in sections] == ["llm01", "llm02"]
        assert sections[0].name == "Prompt Injection"
        assert sections[1].name == "Insecure Output Handling"
        assert "Body text for one line A." in sections[0].content

    def test_no_matching_headers_returns_empty_list(self):
        assert _parse_sections("Just a preamble with no risk sections.") == []
