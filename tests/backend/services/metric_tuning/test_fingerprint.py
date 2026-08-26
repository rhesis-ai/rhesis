"""Unit tests for the run fingerprint — whether a run predates the metric it scored.

A fingerprint covers the fields that decide a verdict and nothing else. The two
halves of that are equally load-bearing: renaming a metric must not stale a run,
and editing the evaluation prompt by hand must (domain.local/adr/0006).

A pure function over a metric and a stored summary, so it is tested directly
rather than through a run. Run with:
python -m pytest tests/backend/services/metric_tuning/test_fingerprint.py -v
"""

from types import SimpleNamespace

from rhesis.backend.app.schemas.metric_tuning_metadata import MetricTuningRunSummary
from rhesis.backend.app.services.metric_tuning.fingerprint import (
    metric_fingerprint,
    run_predates_metric,
)


def _metric(**overrides):
    """A metric-shaped object carrying only what the fingerprint reads."""
    fields = {
        "name": "Toxicity",
        "description": "How toxic the answer is.",
        "evaluation_prompt": "Score how toxic the answer is.",
        "evaluation_steps": "Step 1:\nRead the answer.",
        "reasoning": "Quote the phrase you judged.",
        "explanation": "A fail means the answer is toxic.",
        "threshold": 0.5,
        "threshold_operator": ">=",
        "passing_categories": ["helpful"],
        "categories": ["helpful", "harmful"],
        "score_type": "numeric",
        "min_score": 0.0,
        "max_score": 1.0,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


class TestMetricFingerprint:
    """What the digest covers, and what it deliberately ignores."""

    def test_the_same_metric_fingerprints_the_same(self):
        assert metric_fingerprint(_metric()) == metric_fingerprint(_metric())

    def test_editing_the_evaluation_prompt_changes_it(self):
        assert metric_fingerprint(_metric()) != metric_fingerprint(
            _metric(evaluation_prompt="Score how helpful the answer is.")
        )

    def test_editing_the_evaluation_steps_changes_it(self):
        assert metric_fingerprint(_metric()) != metric_fingerprint(
            _metric(evaluation_steps="Step 1:\nRead it twice.")
        )

    def test_moving_the_threshold_changes_it(self):
        assert metric_fingerprint(_metric()) != metric_fingerprint(_metric(threshold=0.8))

    def test_changing_the_threshold_operator_changes_it(self):
        assert metric_fingerprint(_metric()) != metric_fingerprint(_metric(threshold_operator=">"))

    def test_changing_the_passing_categories_changes_it(self):
        assert metric_fingerprint(_metric()) != metric_fingerprint(
            _metric(passing_categories=["helpful", "harmful"])
        )

    def test_renaming_the_metric_does_not_change_it(self):
        """The whole reason this is not the metric's ``updated_at``."""
        assert metric_fingerprint(_metric()) == metric_fingerprint(_metric(name="Toxicity v2"))

    def test_rewriting_the_prose_fields_does_not_change_it(self):
        """None of these reach the judge, so none of them stale a run."""
        assert metric_fingerprint(_metric()) == metric_fingerprint(
            _metric(
                description="Rewritten.",
                reasoning="Rewritten.",
                explanation="Rewritten.",
            )
        )

    def test_reordering_the_passing_categories_does_not_change_it(self):
        """The same passing set, so the same decision for every verdict."""
        one = _metric(passing_categories=["helpful", "polite"])
        other = _metric(passing_categories=["polite", "helpful"])
        assert metric_fingerprint(one) == metric_fingerprint(other)

    def test_recasing_the_passing_categories_does_not_change_it(self):
        """Buckets are compared case-insensitively, so casing decides nothing."""
        assert metric_fingerprint(_metric()) == metric_fingerprint(
            _metric(passing_categories=["Helpful"])
        )

    def test_an_absent_field_and_an_empty_one_fingerprint_alike(self):
        assert metric_fingerprint(_metric(evaluation_steps=None)) == metric_fingerprint(
            _metric(evaluation_steps="")
        )

    def test_a_threshold_written_differently_fingerprints_alike(self):
        assert metric_fingerprint(_metric(threshold=0.5)) == metric_fingerprint(
            _metric(threshold=0.50)
        )


class TestRunPredatesMetric:
    def test_a_run_of_the_current_metric_does_not_predate_it(self):
        metric = _metric()
        summary = MetricTuningRunSummary(metric_fingerprint=metric_fingerprint(metric))
        assert run_predates_metric(summary, metric) is False

    def test_a_run_of_an_earlier_prompt_predates_it(self):
        summary = MetricTuningRunSummary(metric_fingerprint=metric_fingerprint(_metric()))
        edited = _metric(evaluation_prompt="Score how helpful the answer is.")
        assert run_predates_metric(summary, edited) is True

    def test_a_run_with_no_fingerprint_is_unknown_rather_than_stale(self):
        """Runs stored before this existed must not all read as out of date."""
        assert run_predates_metric(MetricTuningRunSummary(), _metric()) is False

    def test_a_blank_fingerprint_is_unknown_too(self):
        summary = MetricTuningRunSummary(metric_fingerprint="   ")
        assert run_predates_metric(summary, _metric()) is False
