"""Tests for file_import.mapping module."""

from rhesis.backend.app.services.file_import.mapping import (
    auto_map_columns,
    is_llm_available,
    llm_map_columns,
)

# ── auto_map_columns ─────────────────────────────────────────────


class TestAutoMapColumns:
    def test_exact_match(self):
        headers = ["category", "topic", "behavior", "prompt_content"]
        result = auto_map_columns(headers)
        assert result["mapping"]["category"] == "category"
        assert result["mapping"]["topic"] == "topic"
        assert result["mapping"]["behavior"] == "behavior"
        assert result["mapping"]["prompt_content"] == "prompt_content"

    def test_alias_match(self):
        headers = ["question", "cat", "subject", "expected_output"]
        result = auto_map_columns(headers)
        assert result["mapping"].get("question") == "prompt_content"
        assert result["mapping"].get("cat") == "category"
        assert result["mapping"].get("subject") == "topic"
        assert result["mapping"].get("expected_output") == "expected_response"

    def test_case_insensitive_match(self):
        headers = ["Category", "TOPIC", "Prompt_Content"]
        result = auto_map_columns(headers)
        assert result["mapping"]["Category"] == "category"
        assert result["mapping"]["TOPIC"] == "topic"
        assert result["mapping"]["Prompt_Content"] == "prompt_content"

    def test_no_match(self):
        headers = ["xyz", "abc", "123"]
        result = auto_map_columns(headers)
        assert len(result["mapping"]) == 0
        assert result["confidence"] < 0.5

    def test_partial_match(self):
        headers = ["category", "unknown_col", "prompt_content"]
        result = auto_map_columns(headers)
        assert "category" in result["mapping"]
        assert "prompt_content" in result["mapping"]
        assert "unknown_col" not in result["mapping"]

    def test_confidence_full_match(self):
        headers = [
            "category",
            "topic",
            "behavior",
            "prompt_content",
        ]
        result = auto_map_columns(headers)
        # High confidence when all required fields are matched
        assert result["confidence"] >= 0.7

    def test_confidence_low_match(self):
        headers = ["foo", "bar", "baz", "category"]
        result = auto_map_columns(headers)
        # Lower confidence with minimal matches
        assert result["confidence"] < 0.7

    def test_empty_headers(self):
        result = auto_map_columns([])
        assert result["mapping"] == {}
        assert result["confidence"] == 0.0

    def test_unmatched_headers_reported(self):
        headers = ["category", "unknown_col"]
        result = auto_map_columns(headers)
        assert "unknown_col" in result["unmatched_headers"]

    def test_unmatched_targets_reported(self):
        headers = ["category"]
        result = auto_map_columns(headers)
        assert "topic" in result["unmatched_targets"]
        assert "behavior" in result["unmatched_targets"]


# ── is_llm_available ─────────────────────────────────────────────


class TestIsLlmAvailable:
    def test_no_db_no_user(self):
        assert is_llm_available() is False

    def test_none_db_and_user(self):
        assert is_llm_available(db=None, user=None) is False


# ── llm_map_columns fallback ─────────────────────────────────────


class TestLlmMapColumnsFallback:
    def test_falls_back_to_auto_when_no_llm(self):
        headers = ["category", "prompt_content"]
        result = llm_map_columns(
            headers=headers,
            sample_rows=[{"category": "Safety", "prompt_content": "test"}],
            db=None,
            user=None,
        )
        # Should fall back to auto_map_columns
        assert "mapping" in result
        assert result["mapping"].get("category") == "category"
