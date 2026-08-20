"""Unit tests for `app/services/owasp.py`'s category-summary logic.

No dedicated test file existed for this module before -- the sibling Garak
services (`services/garak/test_probes.py`, `test_taxonomy.py`, ...) each have
one, but this module's `_short_description` heuristic and
`list_category_summaries`'s cache/validation logic had zero coverage.
"""

from unittest.mock import patch

import pytest

from rhesis.backend.app.services.owasp import _short_description, list_category_summaries
from rhesis.sdk.services.owasp_extractor import ReportSection


@pytest.mark.unit
class TestShortDescription:
    def test_extracts_text_under_description_heading(self):
        content = "# LLM01\n## Description\nPrompt injection is bad.\n## Other\nignored"
        assert _short_description(content) == "Prompt injection is bad."

    def test_extracts_text_under_overview_heading(self):
        content = "# LLM01\n## Overview\nAn overview blurb.\n## Other\nignored"
        assert _short_description(content) == "An overview blurb."

    def test_falls_back_to_first_paragraph_when_no_description_or_overview(self):
        content = "# LLM01\n## Examples\nSomething else entirely.\nMore text."
        assert _short_description(content) == "Something else entirely. More text."

    def test_truncates_with_ellipsis_at_max_len(self):
        content = "## Description\n" + ("word " * 100)
        result = _short_description(content, max_len=20)
        assert len(result) <= 20
        assert result.endswith("…")

    def test_empty_content_returns_empty_string(self):
        assert _short_description("") == ""


@pytest.mark.unit
class TestListCategorySummaries:
    def test_raises_for_unknown_framework(self):
        with pytest.raises(ValueError, match="Unknown OWASP framework"):
            list_category_summaries("not-a-framework")

    def test_returns_cached_summaries_without_fetching(self):
        cached = [{"id": "llm01", "name": "Prompt Injection", "description": "d"}]

        with (
            patch("rhesis.backend.app.services.owasp._cache") as mock_cache,
            patch("rhesis.backend.app.services.owasp.fetch_owasp_sections") as mock_fetch,
        ):
            mock_cache.get_sections.return_value = cached

            result = list_category_summaries("llm")

        mock_cache.initialize.assert_called_once()
        mock_fetch.assert_not_called()
        assert result == cached

    def test_fetches_and_caches_on_miss(self):
        sections = [
            ReportSection(id="llm01", name="Prompt Injection", content="## Description\nBad."),
        ]

        with (
            patch("rhesis.backend.app.services.owasp._cache") as mock_cache,
            patch(
                "rhesis.backend.app.services.owasp.fetch_owasp_sections", return_value=sections
            ) as mock_fetch,
        ):
            mock_cache.get_sections.return_value = None

            result = list_category_summaries("llm")

        mock_fetch.assert_called_once()
        assert result == [{"id": "llm01", "name": "Prompt Injection", "description": "Bad."}]
        mock_cache.set_sections.assert_called_once_with("llm", result)
