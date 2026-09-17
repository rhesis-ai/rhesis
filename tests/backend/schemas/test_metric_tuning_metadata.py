"""Tests for the metric tuning JSONB metadata schema.

Covers the contract every call site in crud/metric_tuning.py and
services/metric_tuning/* relies on: parse_* is total (never raises, even on
garbage input), dumping via model_dump(mode="json", exclude_none=True) drops
None fields rather than writing them as null, and unknown keys survive a
read/write round trip because the column is shared with other writers.

Only the machine's ``result`` lives in the column now, latest run only
(domain.local/adr/0004). The human judgements that used to sit beside it are
``annotation`` rows, so a stale ``reviews`` array left behind by an older
deployment is just another foreign key the column has to round-trip untouched.
"""

import pytest

from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningCaseMetadata,
    MetricTuningCaseResult,
    parse_metric_tuning_case_metadata,
)


@pytest.mark.unit
class TestParseIsTotal:
    """parse_metric_tuning_case_metadata never raises, whatever it's handed."""

    @pytest.mark.parametrize("raw", [None, {}])
    def test_none_and_empty_dict_give_defaults(self, raw):
        meta = parse_metric_tuning_case_metadata(raw)

        assert meta == MetricTuningCaseMetadata()

    def test_non_mapping_input_does_not_raise(self):
        meta = parse_metric_tuning_case_metadata("not a dict")

        assert meta == MetricTuningCaseMetadata()

    def test_a_garbage_result_value_does_not_raise(self):
        """A run reading a mangled column has to keep going, not 500."""
        meta = parse_metric_tuning_case_metadata({"result": "not an object"})

        assert meta == MetricTuningCaseMetadata()
        assert meta.result is None


@pytest.mark.unit
class TestTheResult:
    """The latest run's verdict, which is the only thing the column now owns."""

    def test_a_result_round_trips(self):
        raw = {
            "verdict": "0.2",
            "reasoning": "the answer contains an insult",
            "evaluated_at": "2026-08-20T09:00:00+00:00",
        }

        meta = parse_metric_tuning_case_metadata({"result": raw})

        assert meta.model_dump(mode="json", exclude_none=True)["result"] == raw

    def test_default_metadata_dumps_to_nothing_at_all(self):
        """A case nobody has run carries no keys, not a null result."""
        assert MetricTuningCaseMetadata().model_dump(mode="json", exclude_none=True) == {}

    def test_an_error_is_kept_apart_from_a_verdict(self):
        """A failed call is not a verdict a reviewer would reject."""
        meta = parse_metric_tuning_case_metadata({"result": {"error": "provider unreachable"}})

        assert meta.result.error == "provider unreachable"
        assert meta.result.verdict is None

    def test_a_non_string_verdict_is_coerced(self):
        """The metric's score arrives as a number and is stored as its string."""
        meta = parse_metric_tuning_case_metadata({"result": {"verdict": 0.2}})

        assert meta.result.verdict == "0.2"


@pytest.mark.unit
class TestAbsentVersusEmpty:
    """None means "key absent", "" means "present but empty" -- both are real states."""

    def test_defaults_are_none_not_empty_string(self):
        meta = MetricTuningCaseMetadata(result={})

        assert meta.result.verdict is None

    def test_empty_string_survives(self):
        meta = parse_metric_tuning_case_metadata({"result": {"reasoning": ""}})

        assert meta.result.reasoning == ""

    def test_dump_omits_none_fields(self):
        """An absent reasoning comes back as no key at all, not as null."""
        meta = parse_metric_tuning_case_metadata({"result": {"verdict": "0.2"}})

        dumped = meta.model_dump(mode="json", exclude_none=True)

        assert dumped["result"] == {"verdict": "0.2"}


@pytest.mark.unit
class TestUnknownKeysRoundTrip:
    """The column is shared, so foreign keys must not be dropped."""

    def test_explorer_written_keys_survive(self):
        """Keys written by other features round-trip untouched."""
        raw = {
            "label": "fail",
            "labeler": "user",
            "model_score": 0.0,
        }

        meta = parse_metric_tuning_case_metadata(raw)
        dumped = meta.model_dump(mode="json", exclude_none=True)

        assert dumped["label"] == "fail"
        assert dumped["labeler"] == "user"
        assert dumped["model_score"] == 0.0

    def test_a_legacy_reviews_array_survives_untouched(self):
        """The judgements are annotation rows now, but PR-5 is what clears the
        array -- until then it is a foreign key like any other and a run that
        rewrites the result must not eat it."""
        reviews = [{"decision": "rejected", "comment": "plainly toxic", "verdict": "pass"}]

        meta = parse_metric_tuning_case_metadata({"reviews": reviews})
        meta.result = MetricTuningCaseResult(verdict="fail")
        dumped = meta.model_dump(mode="json", exclude_none=True)

        assert dumped["reviews"] == reviews
        assert dumped["result"] == {"verdict": "fail"}

    def test_unknown_keys_on_a_result_survive(self):
        meta = parse_metric_tuning_case_metadata({"result": {"verdict": "0.2", "took_ms": 91}})

        dumped = meta.model_dump(mode="json", exclude_none=True)

        assert dumped["result"]["took_ms"] == 91

    def test_assignment_is_validated(self):
        result = MetricTuningCaseResult()

        result.verdict = 42

        assert result.verdict == "42"
