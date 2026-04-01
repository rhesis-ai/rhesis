"""Tests for file_import.transforms module."""

from rhesis.backend.app.services.file_import.transforms import (
    apply_mapping,
    detect_test_type_mismatch,
    normalize_row,
)

# ── apply_mapping ────────────────────────────────────────────────


class TestApplyMapping:
    def test_renames_columns(self):
        rows = [{"Question": "hi", "Cat": "Safety"}]
        result = apply_mapping(rows, {"Question": "prompt_content", "Cat": "category"})
        assert result[0]["prompt_content"] == "hi"
        assert result[0]["category"] == "Safety"

    def test_unmapped_keys_preserved(self):
        rows = [{"prompt": {"content": "hi"}, "extra": "val"}]
        result = apply_mapping(rows, {})
        assert result[0]["prompt"]["content"] == "hi"
        assert result[0]["extra"] == "val"

    def test_empty_mapping_returns_original(self):
        rows = [{"a": 1}]
        assert apply_mapping(rows, {}) == rows

    def test_multiple_rows(self):
        rows = [{"X": "a"}, {"X": "b"}]
        result = apply_mapping(rows, {"X": "category"})
        assert result[0]["category"] == "a"
        assert result[1]["category"] == "b"


# ── normalize_row ────────────────────────────────────────────────


class TestNormalizeRow:
    def test_flat_to_nested_prompt(self):
        row = {
            "prompt_content": "test prompt",
            "expected_response": "response",
            "language_code": "en",
            "category": "Safety",
        }
        result = normalize_row(row)
        assert result["prompt"] == {
            "content": "test prompt",
            "expected_response": "response",
            "language_code": "en",
        }
        assert "prompt_content" not in result
        assert "expected_response" not in result
        assert "language_code" not in result

    def test_already_nested_prompt_unchanged(self):
        row = {"prompt": {"content": "already nested"}, "category": "Safety"}
        result = normalize_row(row)
        assert result["prompt"]["content"] == "already nested"

    def test_flat_fields_merged_into_existing_prompt(self):
        row = {
            "prompt": {"content": "hello"},
            "expected_response": "world",
            "language_code": "de",
        }
        result = normalize_row(row)
        assert result["prompt"]["expected_response"] == "world"
        assert result["prompt"]["language_code"] == "de"

    def test_prompt_content_dict_unwrapped(self):
        row = {"prompt_content": {"content": "actual text"}, "category": "Safety"}
        result = normalize_row(row)
        assert result["prompt"]["content"] == "actual text"
        assert isinstance(result["prompt"]["content"], str)

    def test_double_nested_prompt_flattened(self):
        row = {
            "prompt": {"content": {"content": "deep text", "language_code": "fr"}},
            "category": "Safety",
        }
        result = normalize_row(row)
        assert result["prompt"]["content"] == "deep text"
        assert result["prompt"]["language_code"] == "fr"

    def test_default_test_type_single_turn(self):
        result = normalize_row({"prompt_content": "x"})
        assert result["test_type"] == "Single-Turn"

    def test_default_test_type_multi_turn(self):
        result = normalize_row({"prompt_content": "x"}, default_test_type="Multi-Turn")
        assert result["test_type"] == "Multi-Turn"

    def test_existing_test_type_not_overwritten(self):
        result = normalize_row(
            {"prompt_content": "x", "test_type": "Multi-Turn"},
            default_test_type="Single-Turn",
        )
        assert result["test_type"] == "Multi-Turn"

    def test_test_configuration_json_string_parsed(self):
        row = {
            "test_configuration": '{"goal": "Test", "instructions": "Do X"}',
        }
        result = normalize_row(row)
        assert result["test_configuration"] == {"goal": "Test", "instructions": "Do X"}

    def test_test_configuration_invalid_json_left_as_string(self):
        row = {"test_configuration": "not json"}
        result = normalize_row(row)
        assert result["test_configuration"] == "not json"


# ── detect_test_type_mismatch ────────────────────────────────────


class TestDetectTestTypeMismatch:
    def _multi_turn_row(self):
        return {"goal": "Probe the model", "category": "Safety", "topic": "T", "behavior": "B"}

    def _single_turn_row(self):
        return {"prompt_content": "Hello", "category": "Safety", "topic": "T", "behavior": "B"}

    def test_no_mismatch_single_turn(self):
        rows = [self._single_turn_row()] * 5
        detected, warning = detect_test_type_mismatch(rows, "Single-Turn")
        assert detected == "Single-Turn"
        assert warning is None

    def test_no_mismatch_multi_turn(self):
        rows = [self._multi_turn_row()] * 5
        detected, warning = detect_test_type_mismatch(rows, "Multi-Turn")
        assert detected == "Multi-Turn"
        assert warning is None

    def test_mismatch_single_selected_but_multi_content(self):
        rows = [self._multi_turn_row()] * 8 + [self._single_turn_row()] * 2
        detected, warning = detect_test_type_mismatch(rows, "Single-Turn")
        assert detected == "Multi-Turn"
        assert warning is not None
        assert "Single-Turn" in warning
        assert "Multi-Turn" in warning

    def test_mismatch_multi_selected_but_single_content(self):
        rows = [self._single_turn_row()] * 8 + [self._multi_turn_row()] * 2
        detected, warning = detect_test_type_mismatch(rows, "Multi-Turn")
        assert detected == "Single-Turn"
        assert warning is not None
        assert "Multi-Turn" in warning
        assert "Single-Turn" in warning

    def test_ambiguous_returns_no_warning(self):
        rows = [self._multi_turn_row()] * 3 + [self._single_turn_row()] * 3
        # Neither exceeds 50 % majority
        _, warning = detect_test_type_mismatch(rows, "Single-Turn")
        assert warning is None

    def test_empty_rows_returns_no_warning(self):
        detected, warning = detect_test_type_mismatch([], "Single-Turn")
        assert detected == "Single-Turn"
        assert warning is None

    def test_warning_contains_percentage(self):
        rows = [self._multi_turn_row()] * 10
        _, warning = detect_test_type_mismatch(rows, "Single-Turn")
        assert "100%" in warning

    def test_multi_turn_indicators(self):
        """Each multi-turn field independently triggers detection."""
        for field in ("goal", "instructions", "restrictions", "scenario", "min_turns", "max_turns"):
            rows = [{field: "value"}] * 10
            detected, _ = detect_test_type_mismatch(rows, "Single-Turn")
            assert detected == "Multi-Turn", f"Expected Multi-Turn for field '{field}'"
