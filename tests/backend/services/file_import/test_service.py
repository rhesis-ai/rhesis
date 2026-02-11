"""Tests for file_import.service module (orchestrator)."""

import json

import pytest

from rhesis.backend.app.services.file_import.service import (
    ImportService,
    _apply_mapping,
    _normalize_row,
    _rows_to_test_data,
)
from rhesis.backend.app.services.file_import.storage import (
    ImportSessionStore,
)


@pytest.fixture(autouse=True)
def clear_sessions():
    """Ensure a clean session store for each test."""
    ImportSessionStore._sessions.clear()
    yield
    ImportSessionStore._sessions.clear()


# ── _apply_mapping ───────────────────────────────────────────────


class TestApplyMapping:
    def test_renames_columns(self):
        rows = [{"Question": "hi", "Cat": "Safety"}]
        mapping = {"Question": "prompt_content", "Cat": "category"}
        result = _apply_mapping(rows, mapping)
        assert result[0]["prompt_content"] == "hi"
        assert result[0]["category"] == "Safety"

    def test_unmapped_preserved(self):
        rows = [{"prompt": {"content": "hi"}, "extra": "val"}]
        mapping = {}
        result = _apply_mapping(rows, mapping)
        assert result[0]["prompt"]["content"] == "hi"
        assert result[0]["extra"] == "val"

    def test_empty_mapping(self):
        rows = [{"a": 1}]
        result = _apply_mapping(rows, {})
        assert result == rows


# ── _normalize_row ───────────────────────────────────────────────


class TestNormalizeRow:
    def test_flat_to_nested(self):
        row = {
            "prompt_content": "test prompt",
            "expected_response": "response",
            "language_code": "en",
            "category": "Safety",
        }
        result = _normalize_row(row)
        assert "prompt" in result
        assert result["prompt"]["content"] == "test prompt"
        assert result["prompt"]["expected_response"] == "response"
        assert result["prompt"]["language_code"] == "en"
        assert "prompt_content" not in result

    def test_already_nested(self):
        row = {
            "prompt": {"content": "already nested"},
            "category": "Safety",
        }
        result = _normalize_row(row)
        assert result["prompt"]["content"] == "already nested"

    def test_prompt_content_is_dict(self):
        """When prompt_content is a dict like {"content": "text"},
        it should be unwrapped to avoid double-nesting."""
        row = {
            "prompt_content": {"content": "actual text"},
            "category": "Safety",
        }
        result = _normalize_row(row)
        assert result["prompt"]["content"] == "actual text"
        assert isinstance(result["prompt"]["content"], str)

    def test_double_nested_prompt_content(self):
        """Prompt dict with content that is itself a dict should flatten."""
        row = {
            "prompt": {"content": {"content": "actual text", "language_code": "fr"}},
            "category": "Safety",
        }
        result = _normalize_row(row)
        assert result["prompt"]["content"] == "actual text"
        assert result["prompt"]["language_code"] == "fr"
        assert isinstance(result["prompt"]["content"], str)

    def test_default_test_type(self):
        row = {"prompt_content": "test", "category": "Safety"}
        result = _normalize_row(row)
        assert result["test_type"] == "Single-Turn"

    def test_default_test_type_multi_turn(self):
        row = {"prompt_content": "test", "category": "Safety"}
        result = _normalize_row(row, default_test_type="Multi-Turn")
        assert result["test_type"] == "Multi-Turn"

    def test_preserves_test_type(self):
        """Row-level test_type takes precedence over default."""
        row = {
            "prompt_content": "test",
            "test_type": "Multi-Turn",
        }
        result = _normalize_row(row)
        assert result["test_type"] == "Multi-Turn"

    def test_row_test_type_overrides_default(self):
        """Row-level test_type takes precedence over default."""
        row = {
            "prompt_content": "test",
            "test_type": "Single-Turn",
        }
        result = _normalize_row(row, default_test_type="Multi-Turn")
        assert result["test_type"] == "Single-Turn"

    def test_parses_test_configuration_json_string(self):
        """test_configuration as JSON string (e.g. from CSV) is parsed to dict."""
        row = {
            "category": "Safety",
            "topic": "Content",
            "behavior": "Refusal",
            "test_type": "Multi-Turn",
            "test_configuration": '{"goal": "Test goal", "instructions": "Do X"}',
        }
        result = _normalize_row(row)
        assert result["test_configuration"] == {
            "goal": "Test goal",
            "instructions": "Do X",
        }


# ── _rows_to_test_data ──────────────────────────────────────────


class TestRowsToTestData:
    def test_converts_rows(self):
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt": {"content": "test"},
            }
        ]
        result = _rows_to_test_data(rows)
        assert len(result) == 1
        assert result[0]["category"] == "Safety"
        assert result[0]["prompt"]["content"] == "test"

    def test_skips_empty_rows(self):
        rows = [
            {},
            {"category": "", "topic": "", "behavior": ""},
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt": {"content": "valid"},
            },
        ]
        result = _rows_to_test_data(rows)
        assert len(result) == 1

    def test_double_nested_prompt_flattened(self):
        """Prompt with double-nested content dict should be flattened."""
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt": {
                    "content": {"content": "actual text"},
                },
            }
        ]
        result = _rows_to_test_data(rows)
        assert len(result) == 1
        assert result[0]["prompt"]["content"] == "actual text"
        assert isinstance(result[0]["prompt"]["content"], str)

    def test_defaults_for_missing(self):
        rows = [
            {
                "prompt": {"content": "test"},
            }
        ]
        result = _rows_to_test_data(rows)
        assert len(result) == 1
        assert result[0]["category"] == "Uncategorized"
        assert result[0]["topic"] == "General"
        assert result[0]["behavior"] == "Default"

    def test_test_configuration_json_string_parsed(self):
        """test_configuration as JSON string (from CSV) is parsed to dict."""
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "test_type": "Multi-Turn",
                "test_configuration": '{"goal": "Probe the model", "instructions": "Ask"}',
            }
        ]
        result = _rows_to_test_data(rows)
        assert len(result) == 1
        assert result[0]["test_configuration"] == {
            "goal": "Probe the model",
            "instructions": "Ask",
        }


# ── ImportService.analyze ────────────────────────────────────────


class TestImportServiceAnalyze:
    def test_analyze_json(self):
        data = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt_content": "test",
            }
        ]
        file_bytes = json.dumps(data).encode("utf-8")
        result = ImportService.analyze(
            file_bytes=file_bytes,
            filename="tests.json",
        )
        assert "import_id" in result
        assert result["file_info"]["format"] == "json"
        assert "headers" in result
        assert "suggested_mapping" in result

    def test_analyze_csv(self):
        csv_content = "category,topic,behavior,prompt_content\nSafety,Content,Refusal,test\n"
        result = ImportService.analyze(
            file_bytes=csv_content.encode("utf-8"),
            filename="tests.csv",
        )
        assert result["file_info"]["format"] == "csv"
        assert "category" in result["headers"]

    def test_analyze_creates_session(self):
        data = [{"category": "Safety"}]
        file_bytes = json.dumps(data).encode("utf-8")
        result = ImportService.analyze(
            file_bytes=file_bytes,
            filename="tests.json",
        )
        session = ImportSessionStore.get_session(result["import_id"])
        assert session is not None
        assert session.filename == "tests.json"

    def test_analyze_llm_available_false_without_db(self):
        data = [{"category": "Safety"}]
        file_bytes = json.dumps(data).encode("utf-8")
        result = ImportService.analyze(
            file_bytes=file_bytes,
            filename="tests.json",
            db=None,
            user=None,
        )
        assert result["llm_available"] is False


# ── ImportService.parse ──────────────────────────────────────────


class TestImportServiceParse:
    def _setup_session(self):
        data = [
            {
                "Question": "test prompt",
                "Cat": "Safety",
                "Subject": "Content",
                "Behavior": "Refusal",
            }
        ]
        file_bytes = json.dumps(data).encode("utf-8")
        result = ImportService.analyze(
            file_bytes=file_bytes,
            filename="tests.json",
        )
        return result["import_id"]

    def test_parse_with_mapping(self):
        import_id = self._setup_session()
        mapping = {
            "Question": "prompt_content",
            "Cat": "category",
            "Subject": "topic",
            "Behavior": "behavior",
        }
        result = ImportService.parse(import_id, mapping)
        assert result["total_rows"] == 1
        assert "validation_summary" in result
        assert "preview" in result

    def test_parse_with_multi_turn_type(self):
        import_id = self._setup_session()
        mapping = {
            "Question": "prompt_content",
            "Cat": "category",
            "Subject": "topic",
            "Behavior": "behavior",
        }
        ImportService.parse(import_id, mapping, test_type="Multi-Turn")
        # All rows should default to Multi-Turn
        session = ImportSessionStore.get_session(import_id)
        assert session is not None
        for row in session.parsed_rows:
            assert row["test_type"] == "Multi-Turn"

    def test_parse_defaults_to_single_turn(self):
        import_id = self._setup_session()
        mapping = {
            "Question": "prompt_content",
            "Cat": "category",
            "Subject": "topic",
            "Behavior": "behavior",
        }
        ImportService.parse(import_id, mapping)
        session = ImportSessionStore.get_session(import_id)
        assert session is not None
        for row in session.parsed_rows:
            assert row["test_type"] == "Single-Turn"

    def test_parse_nonexistent_session(self):
        with pytest.raises(ValueError, match="not found"):
            ImportService.parse("nonexistent", {})


# ── ImportService.preview ────────────────────────────────────────


class TestImportServicePreview:
    def test_preview_pagination(self):
        data = [{"category": f"Cat{i}", "prompt_content": f"p{i}"} for i in range(30)]
        file_bytes = json.dumps(data).encode("utf-8")
        result = ImportService.analyze(file_bytes=file_bytes, filename="test.json")
        ImportService.parse(
            result["import_id"],
            {"category": "category", "prompt_content": "prompt_content"},
        )
        page = ImportService.preview(result["import_id"], page=1, page_size=10)
        assert page is not None
        assert page["total_rows"] == 30
        assert len(page["rows"]) == 10


# ── ImportService.cancel ─────────────────────────────────────────


class TestImportServiceCancel:
    def test_cancel(self):
        data = [{"x": 1}]
        file_bytes = json.dumps(data).encode("utf-8")
        result = ImportService.analyze(file_bytes=file_bytes, filename="test.json")
        assert ImportService.cancel(result["import_id"]) is True
        assert ImportSessionStore.get_session(result["import_id"]) is None

    def test_cancel_nonexistent(self):
        assert ImportService.cancel("nope") is False
