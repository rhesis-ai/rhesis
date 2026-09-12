"""Unit tests for test-result annotation override logic.

Tests the annotation_override.test_result module: metric key resolution,
evaluable-content detection, apply/revert/recalculate override semantics.
"""

from typing import ClassVar
from unittest.mock import patch

from rhesis.backend.app.constants import AnnotationTarget
from rhesis.backend.app.outcomes import Execution, Verdict
from rhesis.backend.app.services.annotation_override.common import is_passed_status
from rhesis.backend.app.services.annotation_override.test_result import (
    _apply_metric_override,
    _find_metric_key,
    _has_evaluable_content,
    apply_override,
    recalculate_overall_status,
)


class _MockAnnotation:
    def __init__(self, id="ann-1", user_id="user-1", target_type="test_result",
                 target_reference=None, status_id=None, status_name="Pass"):
        self.id = id
        self.user_id = user_id
        self.target_type = target_type
        self.target_reference = target_reference
        self.status_id = status_id
        self.status = type("Status", (), {"id": status_id, "name": status_name})()


class TestIsPassedStatus:
    def test_pass_is_passed(self):
        assert is_passed_status("Pass") is True

    def test_fail_is_not_passed(self):
        assert is_passed_status("Fail") is False


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
    @patch("rhesis.backend.app.services.annotation_override.test_result.flag_modified")
    def test_applies_override_with_slug_reference(self, _mock_flag_modified):
        class StubResult:
            test_metrics: ClassVar[dict] = {
                "metrics": {
                    "Bias Detection": {"is_successful": False},
                }
            }

        result = StubResult()
        _apply_metric_override(result, "bias-detection", True, "review-1", "user-1", "2026-01-01T00:00:00Z")

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
        class StubResult:
            test_metrics = None
            test_output = "some raw string"

        assert _has_evaluable_content(StubResult()) is False


class TestApplyOverrideTestResultTarget:
    @patch("rhesis.backend.app.services.annotation_override.test_result._apply_outcome")
    def test_override_on_evaluable_result_sets_pass_fail(self, mock_apply_outcome):
        class StubResult:
            test_metrics: ClassVar[dict] = {"metrics": {"Accuracy": {"is_successful": False}}}
            test_output = None

        result = StubResult()
        annotation = _MockAnnotation(target_type=AnnotationTarget.TEST_RESULT, status_name="Pass")
        apply_override(result, annotation, {"name": "Pass"})

        mock_apply_outcome.assert_called_once_with(result, Execution.OK, Verdict.PASS)

    @patch("rhesis.backend.app.services.annotation_override.test_result._apply_outcome")
    def test_override_on_result_with_no_evaluable_content_forces_error(self, mock_apply_outcome):
        class StubResult:
            test_metrics = None
            test_output = None

        result = StubResult()
        annotation = _MockAnnotation(target_type=AnnotationTarget.TEST_RESULT, status_name="Pass")
        apply_override(result, annotation, {"name": "Pass"})

        mock_apply_outcome.assert_called_once_with(result, Execution.ERROR, None)


class TestRecalculateOverallStatusNoContent:
    @patch("rhesis.backend.app.services.annotation_override.test_result._apply_outcome")
    def test_metrics_less_result_resets_to_error(self, mock_apply_outcome):
        class StubResult:
            test_metrics = None
            test_output = None

        result = StubResult()
        recalculate_overall_status(result)

        mock_apply_outcome.assert_called_once_with(result, Execution.ERROR, None)
