"""Unit tests for test-result review override metric key resolution."""

from typing import ClassVar
from unittest.mock import patch

from rhesis.backend.app.constants import REVIEW_TARGET_TEST_RESULT
from rhesis.backend.app.outcomes import Execution, Verdict
from rhesis.backend.app.services.review_override import (
    _apply_metric_override,
    _find_metric_key,
    _has_evaluable_content,
    apply_review_override,
    recalculate_overall_status,
)


class TestFindMetricKey:
    def test_exact_match(self):
        metrics = {"Bias Detection": {"is_successful": False}}
        assert _find_metric_key(metrics, "Bias Detection") == "Bias Detection"

    def test_slug_reference_matches_display_name_key(self):
        metrics = {"Bias Detection": {"is_successful": False}}
        assert _find_metric_key(metrics, "bias-detection") == "Bias Detection"

    def test_missing_metric_returns_none(self):
        metrics = {"Accuracy": {"is_successful": True}}
        assert _find_metric_key(metrics, "Bias Detection") is None


class TestApplyMetricOverride:
    @patch("rhesis.backend.app.services.review_override.flag_modified")
    def test_applies_override_with_slug_reference(self, _mock_flag_modified):
        class StubResult:
            test_metrics: ClassVar[dict] = {
                "metrics": {
                    "Bias Detection": {"is_successful": False},
                }
            }

        result = StubResult()
        user = type("User", (), {"id": "user-1"})()

        _apply_metric_override(
            result,
            "bias-detection",
            True,
            "review-1",
            user,
            "2026-01-01T00:00:00Z",
        )

        metric = result.test_metrics["metrics"]["Bias Detection"]
        assert metric["is_successful"] is True
        assert metric["override"]["original_value"] is False
        assert metric["override"]["review_id"] == "review-1"


class TestHasEvaluableContent:
    def test_no_metrics_no_goal_evaluation_is_not_evaluable(self):
        class StubResult:
            test_metrics = None
            test_output = None

        assert _has_evaluable_content(StubResult()) is False

    def test_empty_metrics_dict_is_not_evaluable(self):
        class StubResult:
            test_metrics: ClassVar[dict] = {"metrics": {}}
            test_output = None

        assert _has_evaluable_content(StubResult()) is False

    def test_metrics_present_is_evaluable(self):
        class StubResult:
            test_metrics: ClassVar[dict] = {"metrics": {"Accuracy": {"is_successful": True}}}
            test_output = None

        assert _has_evaluable_content(StubResult()) is True

    def test_goal_evaluation_without_metrics_is_evaluable(self):
        class StubResult:
            test_metrics = None
            test_output: ClassVar[dict] = {"goal_evaluation": {"achieved": True}}

        assert _has_evaluable_content(StubResult()) is True

    def test_non_dict_test_output_is_not_evaluable(self):
        """A stringified test_output (a legacy shape) must not be read as
        having a goal_evaluation key.
        """

        class StubResult:
            test_metrics = None
            test_output = "some raw string"

        assert _has_evaluable_content(StubResult()) is False


class TestApplyReviewOverrideTestResultTarget:
    """A review targeting the whole test result (REVIEW_TARGET_TEST_RESULT,
    reference=None) can correct a verdict, but must not fabricate one on a
    result that never produced evaluable output -- see _has_evaluable_content.
    """

    @patch("rhesis.backend.app.services.review_override._apply_outcome")
    def test_review_on_evaluable_result_sets_pass_fail(self, mock_apply_outcome):
        class StubResult:
            test_metrics: ClassVar[dict] = {"metrics": {"Accuracy": {"is_successful": False}}}
            test_output = None

        result = StubResult()
        user = type("User", (), {"id": "user-1"})()

        apply_review_override(
            result, REVIEW_TARGET_TEST_RESULT, None, {"name": "Pass"}, user, "review-1"
        )

        mock_apply_outcome.assert_called_once_with(result, Execution.OK, Verdict.PASS)

    @patch("rhesis.backend.app.services.review_override._apply_outcome")
    def test_review_on_result_with_no_evaluable_content_forces_error(self, mock_apply_outcome):
        class StubResult:
            test_metrics = None
            test_output = None

        result = StubResult()
        user = type("User", (), {"id": "user-1"})()

        apply_review_override(
            result, REVIEW_TARGET_TEST_RESULT, None, {"name": "Pass"}, user, "review-1"
        )

        mock_apply_outcome.assert_called_once_with(result, Execution.ERROR, None)


class TestRecalculateOverallStatusNoContent:
    """revert_override's REVIEW_TARGET_TEST_RESULT branch calls this when no
    replacement review remains -- it must reset the row, not leave it stuck
    at whatever the just-deleted review set it to.
    """

    @patch("rhesis.backend.app.services.review_override._apply_outcome")
    def test_metrics_less_turnless_result_resets_to_error(self, mock_apply_outcome):
        class StubResult:
            test_metrics = None
            test_output = None

        result = StubResult()
        recalculate_overall_status(result)

        mock_apply_outcome.assert_called_once_with(result, Execution.ERROR, None)
