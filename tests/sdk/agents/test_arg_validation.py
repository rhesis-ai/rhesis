"""Tests for pre-dispatch tool argument checks."""

import pytest

from rhesis.sdk.agents.arg_validation import find_missing_arguments

# Mirrors the real create_test_set_bulk schema closely enough to exercise
# the nested-item path that produced most of the server 422s.
BULK_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "test_set_type": {"type": "string"},
        "tests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                    "category": {"type": "string"},
                    "topic": {"type": "string"},
                    "prompt": {
                        "anyOf": [
                            {
                                "type": "object",
                                "properties": {"content": {"type": "string"}},
                                "required": ["content"],
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["requirement", "category", "topic"],
            },
        },
    },
    "required": ["name", "test_set_type", "tests"],
}


def _test_item(**overrides):
    item = {"requirement": "b", "category": "c", "topic": "t"}
    item.update(overrides)
    return item


@pytest.mark.unit
class TestFindMissingArguments:
    def test_no_schema_is_a_no_op(self):
        assert find_missing_arguments({"anything": 1}, None) is None
        assert find_missing_arguments({}, {}) is None

    def test_valid_payload_passes(self):
        args = {"name": "n", "test_set_type": "Multi-Turn", "tests": [_test_item()]}
        assert find_missing_arguments(args, BULK_SCHEMA) is None

    def test_missing_top_level_field(self):
        args = {"name": "n", "tests": [_test_item()]}
        error = find_missing_arguments(args, BULK_SCHEMA)
        assert error is not None
        assert "test_set_type" in error

    def test_missing_item_field_is_located_by_index(self):
        args = {
            "name": "n",
            "test_set_type": "Single-Turn",
            "tests": [_test_item(), {"requirement": "b"}],
        }
        error = find_missing_arguments(args, BULK_SCHEMA)
        assert error is not None
        assert "tests[1].category" in error
        assert "tests[1].topic" in error

    def test_nested_object_required_field(self):
        args = {
            "name": "n",
            "test_set_type": "Single-Turn",
            "tests": [_test_item(prompt={"language_code": "en"})],
        }
        error = find_missing_arguments(args, BULK_SCHEMA)
        assert error is not None
        assert "tests[0].prompt.content" in error

    def test_empty_arguments_get_a_distinct_message(self):
        """The silently-dropped-payload case must not read like a normal miss."""
        error = find_missing_arguments({}, BULK_SCHEMA)
        assert error is not None
        assert "No arguments were received" in error
        assert "name" in error

    def test_only_first_items_are_checked(self):
        """Bulk payloads are sampled, not scanned end to end."""
        args = {
            "name": "n",
            "test_set_type": "Single-Turn",
            "tests": [_test_item() for _ in range(20)] + [{"requirement": "b"}],
        }
        assert find_missing_arguments(args, BULK_SCHEMA) is None

    def test_null_counts_as_missing(self):
        args = {"name": None, "test_set_type": "Single-Turn", "tests": [_test_item()]}
        error = find_missing_arguments(args, BULK_SCHEMA)
        assert error is not None
        assert "name" in error

    def test_loose_enum_values_are_not_rejected(self):
        """The API normalises casing, so local checks must not second-guess it."""
        args = {"name": "n", "test_set_type": "multi_turn", "tests": [_test_item()]}
        assert find_missing_arguments(args, BULK_SCHEMA) is None

    def test_empty_list_is_left_to_the_server(self):
        args = {"name": "n", "test_set_type": "Single-Turn", "tests": []}
        assert find_missing_arguments(args, BULK_SCHEMA) is None
