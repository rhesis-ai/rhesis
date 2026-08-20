"""Tests for the metric tuning JSONB metadata schema.

Covers the contract every call site in crud/metric_tuning.py and
services/metric_tuning/* relies on: parse_* is total (never raises, even on
garbage input), dumping via model_dump(mode="json", exclude_none=True) drops
None fields rather than writing them as null, and unknown keys survive a
read/write round trip because the column is shared with other writers.

Two things live in the column and they are opposites. The ``result`` is machine
output, latest run only; the ``reviews`` are human-authored and accumulate,
because their comments are what someone reads when rewriting an evaluation
prompt (domain.local/adr/0005).
"""

import pytest

from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningCaseMetadata,
    MetricTuningReview,
    ReviewDecision,
    parse_metric_tuning_case_metadata,
)

A_REVIEW = {
    "decision": "rejected",
    "comment": "scored a pass, but this is an insult",
    "verdict": "pass",
    "score_type": "binary",
    "reviewer_id": "0f9d4b26-2f9a-4f0e-9b8f-1c2d3e4f5a6b",
    "reviewed_at": "2026-08-20T09:00:00+00:00",
}


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

    def test_garbage_reviews_value_gives_defaults(self):
        """A run reading a mangled column has to keep going, not 500."""
        meta = parse_metric_tuning_case_metadata({"reviews": "not a list"})

        assert meta.reviews == []
        assert meta.result is None

    def test_garbage_inside_a_review_gives_defaults(self):
        meta = parse_metric_tuning_case_metadata({"reviews": [{"decision": "maybe"}]})

        assert meta == MetricTuningCaseMetadata()


@pytest.mark.unit
class TestReviewsAccumulate:
    """The reviews are the point of the feature, so they parse and dump exactly."""

    def test_absent_reviews_parse_to_an_empty_list(self):
        """Callers iterate the list without checking for None first."""
        meta = parse_metric_tuning_case_metadata({"result": {"verdict": "pass"}})

        assert meta.reviews == []

    def test_a_review_round_trips(self):
        meta = parse_metric_tuning_case_metadata({"reviews": [A_REVIEW]})

        dumped = meta.model_dump(mode="json", exclude_none=True)

        assert dumped["reviews"] == [A_REVIEW]

    def test_dump_writes_no_null_keys(self):
        """An accept has no comment, and that comes back as an absent key."""
        meta = MetricTuningCaseMetadata(reviews=[MetricTuningReview(verdict="pass")])

        dumped = meta.model_dump(mode="json", exclude_none=True)

        assert dumped == {"reviews": [{"decision": "accepted", "verdict": "pass"}]}

    def test_default_metadata_dumps_to_an_empty_history(self):
        dumped = MetricTuningCaseMetadata().model_dump(mode="json", exclude_none=True)

        assert dumped == {"reviews": []}
        assert "result" not in dumped


@pytest.mark.unit
class TestEvictable:
    """The history cap drops accepts and never a review someone wrote in."""

    def test_an_accept_is_evictable(self):
        review = MetricTuningReview(decision=ReviewDecision.ACCEPTED, verdict="pass")

        assert review.evictable is True

    def test_a_review_with_a_comment_is_not(self):
        review = MetricTuningReview(
            decision=ReviewDecision.REJECTED,
            comment="scored a pass, but this is an insult",
            verdict="pass",
        )

        assert review.evictable is False

    def test_a_whitespace_comment_does_not_protect_a_review(self):
        """A blank comment is nothing a human wrote, whatever it is made of."""
        review = MetricTuningReview(comment="   ")

        assert review.evictable is True


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

    def test_unknown_keys_on_a_review_survive(self):
        meta = parse_metric_tuning_case_metadata({"reviews": [{**A_REVIEW, "seen_in_ui": True}]})

        dumped = meta.model_dump(mode="json", exclude_none=True)

        assert dumped["reviews"][0]["seen_in_ui"] is True

    def test_assignment_is_validated(self):
        review = MetricTuningReview()

        review.comment = 42

        assert review.comment == "42"
