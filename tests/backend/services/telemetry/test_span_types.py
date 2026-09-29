"""Tests for classify_span_type.

SPAN_TYPE_CASES is shared with the migration's SQL version of the rule
(tests/backend/alembic/test_trace_span_type_migration.py), so the two can't drift.
"""

import pytest

from rhesis.backend.app.services.telemetry.span_types import classify_span_type

OP = "ai.operation.type"
MODEL = "ai.model.name"

# (id, attributes, expected span_type)
SPAN_TYPE_CASES = [
    ("explicit_type", {OP: "tool.invoke"}, "tool.invoke"),
    ("explicit_type_wins_over_model", {OP: "agent.invoke", MODEL: "gpt-4"}, "agent.invoke"),
    ("model_without_type", {MODEL: "gpt-4"}, "llm.invoke"),
    ("neither", {"function.name": "visit_prep_chat"}, "span"),
    ("empty_attributes", {}, "span"),
    ("empty_type_falls_to_model", {OP: "", MODEL: "gpt-4"}, "llm.invoke"),
    ("empty_type_and_model", {OP: "", MODEL: ""}, "span"),
    ("null_type", {OP: None}, "span"),
    ("number_type_is_unset", {OP: 5}, "span"),
    ("bool_type_is_unset", {OP: True, MODEL: "gpt-4"}, "llm.invoke"),
    ("number_model_is_unset", {MODEL: 4}, "span"),
    ("object_model_is_unset", {MODEL: {"name": "gpt-4"}}, "span"),
    ("long_type_is_cut", {OP: "x" * 100}, "x" * 64),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    "attributes,expected",
    [(attrs, expected) for _, attrs, expected in SPAN_TYPE_CASES],
    ids=[case_id for case_id, _, _ in SPAN_TYPE_CASES],
)
def test_classify_span_type(attributes, expected):
    assert classify_span_type(attributes) == expected


@pytest.mark.unit
def test_none_attributes_is_span():
    assert classify_span_type(None) == "span"
