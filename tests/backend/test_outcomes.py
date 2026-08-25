"""The single classifier that replaces the seven duplicated implementations
documented in playground/outcome-model/inventory.md section 4.1.

Every test here pins one specific disagreement those seven copies had, so a
future edit that reintroduces one of them fails loudly.
"""

import pytest

from rhesis.backend.app.outcomes import (
    Execution,
    Outcome,
    Verdict,
    classify_metrics,
    outcome_of,
)


@pytest.mark.unit
class TestOutcomeOf:
    def test_ok_with_each_verdict(self):
        assert outcome_of(Execution.OK, Verdict.PASS) == Outcome.PASS
        assert outcome_of(Execution.OK, Verdict.FAIL) == Outcome.FAIL
        assert outcome_of(Execution.OK, Verdict.INCONCLUSIVE) == Outcome.INCONCLUSIVE

    def test_error_and_cancelled_are_distinct(self):
        """Bug 2 in the inventory: v_test_run_stats folds Cancelled into
        'pending' because it has no branch for it. The model must keep
        error and cancelled as separate, real outcomes.
        """
        assert outcome_of(Execution.ERROR) == Outcome.ERROR
        assert outcome_of(Execution.CANCELLED) == Outcome.CANCELLED
        assert outcome_of(Execution.ERROR) != outcome_of(Execution.CANCELLED)

    def test_not_run_and_running_are_pending(self):
        assert outcome_of(Execution.NOT_RUN) == Outcome.PENDING
        assert outcome_of(Execution.RUNNING) == Outcome.PENDING

    def test_ok_without_a_verdict_raises(self):
        """The whole point of the split: a verdict is not optional once
        execution succeeded. Silently defaulting it is how 'Fail' ends up
        meaning 'we don't actually know'.
        """
        with pytest.raises(ValueError, match="requires a verdict"):
            outcome_of(Execution.OK, None)

    @pytest.mark.parametrize(
        "execution", [Execution.ERROR, Execution.CANCELLED, Execution.NOT_RUN, Execution.RUNNING]
    )
    def test_non_ok_with_a_verdict_raises(self, execution):
        """A verdict on a test that errored, was cancelled, or never ran is
        not stale data to be tolerated -- it means some caller mixed up the
        two axes, and that should fail fast rather than render a plausible
        but meaningless cell.
        """
        with pytest.raises(ValueError, match="must not carry a verdict"):
            outcome_of(execution, Verdict.PASS)


@pytest.mark.unit
class TestClassifyMetrics:
    def test_all_passed(self):
        metrics = {"Accuracy": {"is_successful": True}, "Toxicity": {"is_successful": True}}
        assert classify_metrics(metrics) == (Execution.OK, Verdict.PASS)

    def test_one_failed(self):
        metrics = {"Accuracy": {"is_successful": True}, "Toxicity": {"is_successful": False}}
        assert classify_metrics(metrics) == (Execution.OK, Verdict.FAIL)

    def test_http_error_beats_present_metrics(self):
        """Bug: a stale/partial metrics dict must never paper over an HTTP
        error -- the endpoint's answer was never obtained, so nothing it
        appears to say can be trusted.
        """
        metrics = {"Accuracy": {"is_successful": True}}
        assert classify_metrics(metrics, http_error=True) == (Execution.ERROR, None)

    def test_no_metrics_is_error(self):
        assert classify_metrics({}) == (Execution.ERROR, None)
        assert classify_metrics(None) == (Execution.ERROR, None)

    def test_non_dict_metric_values_ignored_leaving_none_valid(self):
        assert classify_metrics({"Accuracy": "not-a-dict"}) == (Execution.ERROR, None)

    def test_metric_error_is_execution_error_not_fail(self):
        """Bug 5: MetricResultBuilder.error()/.timeout() write
        is_successful=False alongside an error key. Reading only
        is_successful (as every one of the seven old copies did) makes a
        crashed judge model indistinguishable from a real failing metric.
        """
        metrics = {"Accuracy": {"is_successful": False, "error": "Timeout after 30s"}}
        assert classify_metrics(metrics) == (Execution.ERROR, None)

    def test_real_failure_beats_a_sibling_metric_error(self):
        """A definite fail is real signal about the system under test and
        must not be swallowed just because a different metric crashed.
        """
        metrics = {
            "Accuracy": {"is_successful": False},
            "Toxicity": {"is_successful": False, "error": "judge model unavailable"},
        }
        assert classify_metrics(metrics) == (Execution.OK, Verdict.FAIL)

    def test_inconclusive_metric_is_a_distinct_verdict(self):
        """local.py:277 already assigns is_successful=None for a metric
        that reports itself inconclusive. It must not collapse to FAIL.
        """
        metrics = {"Accuracy": {"is_successful": None}}
        assert classify_metrics(metrics) == (Execution.OK, Verdict.INCONCLUSIVE)

    def test_inconclusive_does_not_mask_a_real_failure(self):
        metrics = {
            "Accuracy": {"is_successful": False},
            "Coherence": {"is_successful": None},
        }
        assert classify_metrics(metrics) == (Execution.OK, Verdict.FAIL)

    def test_metric_error_and_inconclusive_together_is_execution_error(self):
        """A crashed metric is a stronger signal that something is wrong
        than a merely-inconclusive one -- ERROR wins over INCONCLUSIVE when
        neither is a real failure.
        """
        metrics = {
            "Accuracy": {"is_successful": None},
            "Toxicity": {"is_successful": False, "error": "boom"},
        }
        assert classify_metrics(metrics) == (Execution.ERROR, None)

    def test_result_is_always_a_valid_outcome_of_input(self):
        """Every branch's output must round-trip through outcome_of without
        raising -- the classifier and the projection must never disagree
        about which combinations are legal.
        """
        for metrics, http_error in [
            ({"a": {"is_successful": True}}, False),
            ({"a": {"is_successful": False}}, False),
            ({"a": {"is_successful": None}}, False),
            ({"a": {"is_successful": False, "error": "x"}}, False),
            ({}, False),
            (None, False),
            ({"a": {"is_successful": True}}, True),
        ]:
            execution, verdict = classify_metrics(metrics, http_error=http_error)
            outcome_of(execution, verdict)  # must not raise
