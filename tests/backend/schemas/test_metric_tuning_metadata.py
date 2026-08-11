"""Tests for the metric tuning JSONB metadata schema.

Covers the contract every call site in crud/metric_tuning.py and
services/metric_tuning/* relies on: parse_* is total (never raises, even on
garbage input), dumping via model_dump(mode="json", exclude_none=True) drops
None fields rather than writing them as null, and unknown keys survive a
read/write round trip because the column is shared with other writers.
"""

import pytest

from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningCaseMetadata,
    parse_metric_tuning_case_metadata,
)


@pytest.mark.unit
class TestParseIsTotal:
    """parse_metric_tuning_case_metadata never raises, whatever it's handed."""

    @pytest.mark.parametrize("raw", [None, {}])
    def test_none_and_empty_dict_give_defaults(self, raw):
        meta = parse_metric_tuning_case_metadata(raw)

        assert meta == MetricTuningCaseMetadata()

    def test_garbage_shaped_input_does_not_raise(self):
        meta = parse_metric_tuning_case_metadata(
            {"output": 12345, "rationale": ["not", "a", "string"]}
        )

        assert isinstance(meta.output, str)
        assert isinstance(meta.rationale, str)

    def test_non_mapping_input_does_not_raise(self):
        meta = parse_metric_tuning_case_metadata("not a dict")

        assert meta == MetricTuningCaseMetadata()


@pytest.mark.unit
class TestAbsentVersusEmpty:
    """None means "key absent", "" means "present but empty" -- both are real states."""

    def test_defaults_are_none_not_empty_string(self):
        meta = MetricTuningCaseMetadata()

        assert meta.output is None
        assert meta.rationale is None

    def test_empty_string_survives(self):
        meta = parse_metric_tuning_case_metadata({"output": "", "rationale": ""})

        assert meta.output == ""
        assert meta.rationale == ""

    def test_dump_omits_none_fields(self):
        dumped = MetricTuningCaseMetadata(output="answer").model_dump(
            mode="json", exclude_none=True
        )

        assert dumped == {"output": "answer"}
        assert "rationale" not in dumped

    def test_dump_keeps_empty_strings(self):
        dumped = MetricTuningCaseMetadata(output="", rationale="").model_dump(
            mode="json", exclude_none=True
        )

        assert dumped == {"output": "", "rationale": ""}


@pytest.mark.unit
class TestUnknownKeysRoundTrip:
    """The column is shared, so foreign keys must not be dropped."""

    def test_explorer_written_keys_survive(self):
        """Explorer writes `output` under the same convention, plus its own keys."""
        raw = {
            "output": "answer",
            "label": "fail",
            "labeler": "user",
            "model_score": 0.0,
        }

        meta = parse_metric_tuning_case_metadata(raw)
        dumped = meta.model_dump(mode="json", exclude_none=True)

        assert dumped["output"] == "answer"
        assert dumped["label"] == "fail"
        assert dumped["labeler"] == "user"
        assert dumped["model_score"] == 0.0

    def test_assignment_is_validated(self):
        meta = MetricTuningCaseMetadata()

        meta.output = 42

        assert meta.output == "42"
