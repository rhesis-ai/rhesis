"""Unit tests for material-change invalidation of tuning reviews.

A review judges one verdict; the next run produces another. These tests pin down
when the two count as the same decision -- the bucket, not the string -- and that
every case where no bucket can be derived falls back to exact equality rather
than to "the review stands".

Pure function, so the metric is a plain unsaved ``models.Metric``: no database.

Run with: python -m pytest tests/backend/services/metric_tuning/test_material_change.py -v
"""

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric_types import ScoreType, ThresholdOperator
from rhesis.backend.app.services.metric_tuning.material_change import review_still_stands


def numeric_metric(threshold=0.5, operator=ThresholdOperator.GREATER_THAN_OR_EQUAL):
    return models.Metric(
        name="Numeric",
        score_type=ScoreType.NUMERIC.value,
        threshold=threshold,
        threshold_operator=operator.value if operator else operator,
    )


def categorical_metric(passing_categories=None):
    return models.Metric(
        name="Categorical",
        score_type=ScoreType.CATEGORICAL.value,
        categories=["excellent", "good", "poor"],
        passing_categories=passing_categories,
    )


def binary_metric():
    return models.Metric(name="Binary", score_type=ScoreType.BINARY.value)


def stands(metric, judged, current, judged_score_type=None):
    return review_still_stands(
        metric,
        judged,
        judged_score_type if judged_score_type is not None else metric.score_type,
        current,
    )


@pytest.mark.unit
class TestNumericThresholdBuckets:
    def test_same_side_of_the_threshold_stands(self):
        """Arithmetic noise is not a decision; the score still passes."""
        assert stands(numeric_metric(threshold=0.5), "0.79", "0.81") is True

    def test_crossing_the_threshold_invalidates(self):
        """The same two numbers, a threshold in between: the metric changed its mind."""
        assert stands(numeric_metric(threshold=0.8), "0.79", "0.81") is False

    def test_landing_on_the_threshold_with_greater_or_equal_passes(self):
        metric = numeric_metric(threshold=0.8, operator=ThresholdOperator.GREATER_THAN_OR_EQUAL)

        assert stands(metric, "0.9", "0.8") is True
        assert stands(metric, "0.79", "0.8") is False

    def test_landing_on_the_threshold_with_greater_than_fails(self):
        metric = numeric_metric(threshold=0.8, operator=ThresholdOperator.GREATER_THAN)

        assert stands(metric, "0.9", "0.8") is False
        assert stands(metric, "0.79", "0.8") is True

    @pytest.mark.parametrize(
        "operator,judged,current,expected",
        [
            (ThresholdOperator.EQUAL, "0.5", "0.5", True),
            (ThresholdOperator.EQUAL, "0.5", "0.6", False),
            (ThresholdOperator.NOT_EQUAL, "0.6", "0.7", True),
            (ThresholdOperator.NOT_EQUAL, "0.6", "0.5", False),
            (ThresholdOperator.LESS_THAN, "0.1", "0.4", True),
            (ThresholdOperator.LESS_THAN, "0.4", "0.5", False),
            (ThresholdOperator.LESS_THAN_OR_EQUAL, "0.4", "0.5", True),
            (ThresholdOperator.LESS_THAN_OR_EQUAL, "0.5", "0.6", False),
            (ThresholdOperator.GREATER_THAN, "0.6", "0.9", True),
            (ThresholdOperator.GREATER_THAN, "0.6", "0.5", False),
            (ThresholdOperator.GREATER_THAN_OR_EQUAL, "0.5", "0.9", True),
            (ThresholdOperator.GREATER_THAN_OR_EQUAL, "0.5", "0.4", False),
        ],
    )
    def test_every_operator_buckets_on_its_own_terms(self, operator, judged, current, expected):
        metric = numeric_metric(threshold=0.5, operator=operator)

        assert stands(metric, judged, current) is expected


@pytest.mark.unit
class TestNumericFallsBackToEquality:
    def test_no_threshold_compares_strings(self):
        metric = numeric_metric(threshold=None)

        assert stands(metric, "0.79", "0.79") is True
        assert stands(metric, "0.79", "0.81") is False

    def test_unparseable_verdict_compares_strings(self):
        """A numeric metric that returned words has no side of the threshold."""
        metric = numeric_metric(threshold=0.5)

        assert stands(metric, "not a number", "not a number") is True
        assert stands(metric, "not a number", "0.9") is False
        assert stands(metric, "0.9", "not a number") is False

    def test_missing_operator_compares_strings(self):
        metric = numeric_metric(threshold=0.5, operator=None)

        assert stands(metric, "0.79", "0.79") is True
        assert stands(metric, "0.79", "0.81") is False

    def test_unrecognized_operator_compares_strings(self):
        metric = numeric_metric(threshold=0.5)
        metric.threshold_operator = "~="

        assert stands(metric, "0.79", "0.79") is True
        assert stands(metric, "0.79", "0.81") is False


@pytest.mark.unit
class TestCategoricalPassingCategories:
    def test_moving_across_the_passing_set_invalidates(self):
        metric = categorical_metric(passing_categories=["excellent", "good"])

        assert stands(metric, "good", "poor") is False

    def test_moving_between_two_passing_categories_stands(self):
        metric = categorical_metric(passing_categories=["excellent", "good"])

        assert stands(metric, "good", "excellent") is True

    def test_the_passing_set_is_matched_case_insensitively(self):
        metric = categorical_metric(passing_categories=["Excellent", "Good"])

        assert stands(metric, "good", "EXCELLENT") is True

    def test_no_passing_categories_compares_strings(self):
        metric = categorical_metric(passing_categories=None)

        assert stands(metric, "good", "good") is True
        assert stands(metric, "good", "excellent") is False

    def test_empty_passing_categories_compares_strings(self):
        metric = categorical_metric(passing_categories=[])

        assert stands(metric, "good", "excellent") is False


@pytest.mark.unit
class TestBinary:
    def test_flipping_the_verdict_invalidates(self):
        assert stands(binary_metric(), "pass", "fail") is False

    def test_casing_and_whitespace_are_not_a_change(self):
        assert stands(binary_metric(), "pass", "  Pass ") is True


@pytest.mark.unit
class TestScoreTypeChange:
    def test_a_changed_score_type_invalidates_an_identical_verdict(self):
        """Whatever "0.8" meant to the old score type, it means something else now."""
        metric = numeric_metric(threshold=0.5)

        assert stands(metric, "0.8", "0.8", judged_score_type=ScoreType.CATEGORICAL.value) is False

    def test_a_review_with_no_recorded_score_type_invalidates(self):
        metric = numeric_metric(threshold=0.5)

        assert review_still_stands(metric, "0.8", None, "0.8") is False


@pytest.mark.unit
class TestMissingVerdicts:
    @pytest.mark.parametrize("current", [None, "", "   "])
    def test_no_current_verdict_invalidates(self, current):
        """Nothing is standing there for the review to have judged."""
        assert stands(numeric_metric(), "0.79", current) is False

    @pytest.mark.parametrize("judged", [None, "", "   "])
    def test_no_judged_verdict_invalidates(self, judged):
        assert stands(numeric_metric(), judged, "0.79") is False


@pytest.mark.unit
class TestUnrecognizedScoreType:
    def test_unknown_score_type_compares_strings(self):
        metric = models.Metric(name="Odd", score_type="tarot", threshold=0.5)

        assert stands(metric, "the tower", "the tower") is True
        assert stands(metric, "the tower", "the star") is False
