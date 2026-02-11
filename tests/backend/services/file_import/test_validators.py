"""Tests for file_import.validators module."""

from rhesis.backend.app.services.file_import.validators import (
    validate_rows,
)


class TestValidateRows:
    def test_valid_single_turn_row(self):
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt": {"content": "test prompt"},
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        assert summary["valid_rows"] == 1
        assert summary["error_count"] == 0
        assert summary["warning_count"] == 0
        assert len(errors[0]) == 0

    def test_missing_category(self):
        rows = [
            {
                "topic": "Content",
                "behavior": "Refusal",
                "prompt": {"content": "test"},
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        assert summary["error_count"] > 0
        assert any(e["field"] == "category" for e in errors[0])

    def test_missing_topic(self):
        rows = [
            {
                "category": "Safety",
                "behavior": "Refusal",
                "prompt": {"content": "test"},
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        assert any(e["field"] == "topic" for e in errors[0])

    def test_missing_behavior(self):
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "prompt": {"content": "test"},
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        assert any(e["field"] == "behavior" for e in errors[0])

    def test_missing_prompt_content(self):
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        assert any(e["field"] == "prompt_content" for e in errors[0])

    def test_prompt_content_flat_format(self):
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt_content": "test prompt",
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        # prompt_content is a flat field recognized by validators
        assert summary["error_count"] == 0

    def test_invalid_test_type_warning(self):
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt": {"content": "test"},
                "test_type": "Unknown-Type",
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        assert summary["warning_count"] > 0
        assert any(w["field"] == "test_type" for w in warnings[0])

    def test_multi_turn_missing_config(self):
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt": {"content": "test"},
                "test_type": "Multi-Turn",
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        assert any(e["field"] == "test_configuration" for e in errors[0])

    def test_multi_turn_missing_goal(self):
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt": {"content": "test"},
                "test_type": "Multi-Turn",
                "test_configuration": {"instructions": "do stuff"},
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        assert any("goal" in e["field"] for e in errors[0])

    def test_multi_turn_valid(self):
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt": {"content": "test"},
                "test_type": "Multi-Turn",
                "test_configuration": {"goal": "test goal"},
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        # Should only have no errors for multi-turn config
        config_errors = [e for e in errors[0] if "test_configuration" in e["field"]]
        assert len(config_errors) == 0

    def test_multi_turn_valid_without_prompt(self):
        """Multi-turn tests do not require prompt content."""
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "test_type": "Multi-Turn",
                "test_configuration": {
                    "goal": "Test the system",
                    "instructions": "Ask for operations",
                    "restrictions": "Decline or bounce",
                    "scenario": "User attempts action",
                },
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        assert summary["valid_rows"] == 1
        assert summary["error_count"] == 0
        assert len(errors[0]) == 0

    def test_multiple_rows(self):
        rows = [
            {
                "category": "Safety",
                "topic": "Content",
                "behavior": "Refusal",
                "prompt": {"content": "ok"},
            },
            {
                "prompt": {"content": "missing fields"},
            },
        ]
        errors, warnings, summary = validate_rows(rows)
        assert summary["total_rows"] == 2
        assert summary["valid_rows"] == 1
        assert len(errors[0]) == 0  # first row is valid
        assert len(errors[1]) > 0  # second row has errors

    def test_empty_rows(self):
        errors, warnings, summary = validate_rows([])
        assert summary["total_rows"] == 0
        assert summary["valid_rows"] == 0
        assert summary["error_count"] == 0

    def test_empty_string_fields(self):
        rows = [
            {
                "category": "",
                "topic": "  ",
                "behavior": "Refusal",
                "prompt": {"content": "test"},
            }
        ]
        errors, warnings, summary = validate_rows(rows)
        assert any(e["field"] == "category" for e in errors[0])
        assert any(e["field"] == "topic" for e in errors[0])
