"""Tests for file_import.builder module."""

from rhesis.backend.app.services.file_import.builder import (
    parse_turn_config,
    rows_to_test_data,
)

# ── parse_turn_config ────────────────────────────────────────────


class TestParseTurnConfig:
    # Single integer → exact turn count (min == max)
    def test_single_integer(self):
        assert parse_turn_config("3") == (3, 3)

    def test_single_integer_with_spaces(self):
        assert parse_turn_config("  5  ") == (5, 5)

    def test_single_integer_with_turns_word(self):
        assert parse_turn_config("3 turns") == (3, 3)
        assert parse_turn_config("1 turn") == (1, 1)

    # Range formats
    def test_hyphen_range(self):
        assert parse_turn_config("2-5") == (2, 5)

    def test_hyphen_range_with_spaces(self):
        assert parse_turn_config("2 - 5") == (2, 5)

    def test_em_dash_range(self):
        assert parse_turn_config("2–5") == (2, 5)

    def test_to_range(self):
        assert parse_turn_config("2 to 5") == (2, 5)

    def test_dot_dot_range(self):
        assert parse_turn_config("2..5") == (2, 5)

    # max-only formats
    def test_max_space(self):
        assert parse_turn_config("max 5") == (None, 5)

    def test_max_colon(self):
        assert parse_turn_config("max:5") == (None, 5)

    def test_max_equals(self):
        assert parse_turn_config("max=5") == (None, 5)

    # min-only formats
    def test_min_space(self):
        assert parse_turn_config("min 2") == (2, None)

    def test_min_colon(self):
        assert parse_turn_config("min:2") == (2, None)

    def test_min_equals(self):
        assert parse_turn_config("min=2") == (2, None)

    # Labelled pairs
    def test_min_max_comma(self):
        assert parse_turn_config("min 2, max 5") == (2, 5)

    def test_min_max_colon(self):
        assert parse_turn_config("min:2 max:5") == (2, 5)

    def test_min_max_equals(self):
        assert parse_turn_config("min=2, max=5") == (2, 5)

    # Case insensitive
    def test_case_insensitive(self):
        assert parse_turn_config("MAX 5") == (None, 5)
        assert parse_turn_config("Min:2") == (2, None)
        assert parse_turn_config("MIN 2, MAX 5") == (2, 5)

    # Unparseable
    def test_unparseable_returns_none(self):
        assert parse_turn_config("lots") is None
        assert parse_turn_config("") is None
        assert parse_turn_config("abc-def") is None


# ── rows_to_test_data: turn config via max_turns field ───────────


class TestRowsToTestDataTurnConfig:
    def _base_row(self, **extra):
        return {
            "category": "Safety",
            "topic": "Content",
            "behavior": "Refusal",
            "test_type": "Multi-Turn",
            "goal": "Test goal",
            **extra,
        }

    def test_single_integer_sets_both(self):
        result = rows_to_test_data([self._base_row(max_turns="3")])
        config = result[0]["test_configuration"]
        assert config["min_turns"] == 3
        assert config["max_turns"] == 3

    def test_range_string_sets_both(self):
        result = rows_to_test_data([self._base_row(max_turns="2-5")])
        config = result[0]["test_configuration"]
        assert config["min_turns"] == 2
        assert config["max_turns"] == 5

    def test_max_only_format(self):
        result = rows_to_test_data([self._base_row(max_turns="max 5")])
        config = result[0]["test_configuration"]
        assert config["max_turns"] == 5
        assert "min_turns" not in config

    def test_explicit_min_turns_not_overwritten_by_range(self):
        """Explicit min_turns column takes precedence over derived min from range."""
        result = rows_to_test_data([self._base_row(min_turns="1", max_turns="2-8")])
        config = result[0]["test_configuration"]
        assert config["min_turns"] == 1  # explicit wins
        assert config["max_turns"] == 8

    def test_integer_max_turns(self):
        result = rows_to_test_data([self._base_row(max_turns=4)])
        config = result[0]["test_configuration"]
        assert config["min_turns"] == 4
        assert config["max_turns"] == 4

    def test_turn_config_with_turns_word(self):
        result = rows_to_test_data([self._base_row(max_turns="5 turns")])
        config = result[0]["test_configuration"]
        assert config["min_turns"] == 5
        assert config["max_turns"] == 5

    def test_empty_max_turns_omitted(self):
        result = rows_to_test_data([self._base_row(max_turns="")])
        config = result[0]["test_configuration"]
        assert "max_turns" not in config
        assert "min_turns" not in config

    def test_unparseable_max_turns_omitted(self):
        result = rows_to_test_data([self._base_row(max_turns="lots")])
        config = result[0]["test_configuration"]
        assert "max_turns" not in config
