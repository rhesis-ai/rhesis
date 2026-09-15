"""Unit tests for trace annotation override logic.

Tests the annotation_override.trace module: apply/revert/recalculate
override semantics for trace metrics and turn overrides.
"""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.outcomes import Execution, Verdict
from rhesis.backend.app.services.annotation_override.common import is_passed_status
from rhesis.backend.app.services.annotation_override.trace import (
    _apply_metric_override,
    _get_all_trace_metric_values,
    apply_override,
    recalculate_overall_status,
    revert_override,
)


class _MockAnnotation:
    def __init__(self, id="ann-1", user_id="user-1", target_type="trace",
                 target_reference=None, status_id=None, status_name="Pass"):
        self.id = id
        self.user_id = user_id
        self.target_type = target_type
        self.target_reference = target_reference
        self.status_id = status_id
        self.status = type("Status", (), {"id": status_id, "name": status_name})()


@pytest.fixture
def mock_trace():
    trace = MagicMock()
    trace.organization_id = "org-123"
    trace.trace_metrics = {
        "turn_metrics": {
            "metrics": {
                "faithfulness": {"is_successful": True, "score": 0.9},
                "relevance": {"is_successful": False, "score": 0.3},
            }
        },
        "conversation_metrics": {
            "metrics": {
                "coherence": {"is_successful": True, "score": 0.95},
            }
        },
    }
    trace.trace_reviews = None
    trace.trace_metrics_status_id = None
    return trace


class TestIsPassedStatus:
    def test_pass_is_passed(self):
        assert is_passed_status("Pass") is True

    def test_fail_is_not_passed(self):
        assert is_passed_status("Fail") is False

    def test_empty_string_is_not_passed(self):
        assert is_passed_status("") is False


class TestGetAllTraceMetricValues:
    def test_collects_all_metrics(self, mock_trace):
        result = _get_all_trace_metric_values(mock_trace.trace_metrics)
        assert len(result) == 3

    def test_empty_trace_metrics(self):
        assert _get_all_trace_metric_values({}) == {}

    def test_only_turn_metrics(self):
        data = {"turn_metrics": {"metrics": {"m1": {"is_successful": True}}}}
        result = _get_all_trace_metric_values(data)
        assert len(result) == 1

    def test_skips_non_dict_values(self):
        data = {"turn_metrics": {"metrics": {"bad": "not a dict", "good": {"is_successful": True}}}}
        result = _get_all_trace_metric_values(data)
        assert len(result) == 1


class TestApplyMetricOverride:
    def test_override_changes_is_successful(self, mock_trace):
        _apply_metric_override(mock_trace, "relevance", True, "rev-1", "user-1", "now")

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["relevance"]
        assert metric["is_successful"] is True
        assert "override" in metric
        assert metric["override"]["original_value"] is False
        assert metric["override"]["annotation_id"] == "rev-1"

    def test_override_removes_when_matching_original(self, mock_trace):
        _apply_metric_override(mock_trace, "faithfulness", True, "rev-1", "user-1", "now")

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["faithfulness"]
        assert metric["is_successful"] is True
        assert "override" not in metric

    def test_override_preserves_original_on_second_override(self, mock_trace):
        _apply_metric_override(mock_trace, "relevance", True, "rev-1", "user-1", "t1")

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["relevance"]
        assert metric["override"]["original_value"] is False

        _apply_metric_override(mock_trace, "relevance", False, "rev-2", "user-1", "t2")
        assert metric["is_successful"] is False
        assert "override" not in metric

    def test_no_op_on_empty_trace_metrics(self):
        trace = MagicMock()
        trace.trace_metrics = None
        _apply_metric_override(trace, "anything", True, "rev-1", "user-1", "now")

    def test_no_op_on_missing_metric(self, mock_trace):
        _apply_metric_override(mock_trace, "nonexistent", True, "rev-1", "user-1", "now")
        assert "nonexistent" not in mock_trace.trace_metrics["turn_metrics"]["metrics"]


class TestApplyOverride:
    @patch("rhesis.backend.app.services.annotation_override.trace._set_pass_fail_status")
    def test_trace_target_sets_status(self, mock_set_status, mock_trace):
        annotation = _MockAnnotation(target_type="trace", status_name="Pass")
        apply_override(mock_trace, annotation, {"name": "Pass"})
        mock_set_status.assert_called_once_with(mock_trace, True)

    @patch("rhesis.backend.app.services.annotation_override.trace.recalculate_overall_status")
    def test_metric_target_overrides_and_recalculates(self, mock_recalc, mock_trace):
        annotation = _MockAnnotation(
            target_type="metric", target_reference="relevance", status_name="Pass"
        )
        apply_override(mock_trace, annotation, {"name": "Pass"})

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["relevance"]
        assert metric["is_successful"] is True
        mock_recalc.assert_called_once_with(mock_trace)


class TestRevertOverride:
    @patch("rhesis.backend.app.services.annotation_override.trace.recalculate_overall_status")
    @patch("rhesis.backend.app.services.annotation_override.trace._set_pass_fail_status")
    def test_revert_trace_with_replacement(self, mock_set_status, mock_recalc, mock_trace):
        replacement = _MockAnnotation(status_name="Fail")
        db = MagicMock()
        revert_override(db, mock_trace, "trace", None, "rev-del", replacement)
        mock_set_status.assert_called_once_with(mock_trace, False)
        mock_recalc.assert_not_called()

    @patch("rhesis.backend.app.services.annotation_override.trace.recalculate_overall_status")
    @patch("rhesis.backend.app.services.annotation_override.trace._set_pass_fail_status")
    def test_revert_trace_no_replacement_recalculates(self, mock_set_status, mock_recalc, mock_trace):
        db = MagicMock()
        revert_override(db, mock_trace, "trace", None, "rev-del", None)
        mock_set_status.assert_not_called()
        mock_recalc.assert_called_once_with(mock_trace)


class TestRecalculateOverallStatus:
    @patch("rhesis.backend.app.services.annotation_override.trace._apply_outcome")
    def test_all_passed_sets_pass(self, mock_apply):
        trace = MagicMock()
        trace.trace_metrics = {
            "turn_metrics": {
                "metrics": {
                    "m1": {"is_successful": True},
                    "m2": {"is_successful": True},
                }
            },
            "conversation_metrics": {"metrics": {}},
        }
        recalculate_overall_status(trace)
        mock_apply.assert_called_once_with(trace, Execution.OK, Verdict.PASS)

    @patch("rhesis.backend.app.services.annotation_override.trace._apply_outcome")
    def test_one_failed_sets_fail(self, mock_apply):
        trace = MagicMock()
        trace.trace_metrics = {
            "turn_metrics": {
                "metrics": {
                    "m1": {"is_successful": True},
                    "m2": {"is_successful": False},
                }
            },
            "conversation_metrics": {"metrics": {}},
        }
        recalculate_overall_status(trace)
        mock_apply.assert_called_once_with(trace, Execution.OK, Verdict.FAIL)

    @patch("rhesis.backend.app.services.annotation_override.trace._apply_outcome")
    def test_no_metrics_resets_to_error(self, mock_apply):
        trace = MagicMock()
        trace.trace_metrics = {
            "turn_metrics": {"metrics": {}},
            "conversation_metrics": {"metrics": {}},
        }
        recalculate_overall_status(trace)
        mock_apply.assert_called_once_with(trace, Execution.ERROR, None)

    @patch("rhesis.backend.app.services.annotation_override.trace._apply_outcome")
    def test_none_trace_metrics_resets_to_error(self, mock_apply):
        trace = MagicMock()
        trace.trace_metrics = None
        recalculate_overall_status(trace)
        mock_apply.assert_called_once_with(trace, Execution.ERROR, None)

    @patch("rhesis.backend.app.services.annotation_override.trace._apply_outcome")
    def test_crashed_metric_sets_error(self, mock_apply):
        trace = MagicMock()
        trace.trace_metrics = {
            "turn_metrics": {"metrics": {"m1": {"is_successful": False, "error": "timeout"}}},
            "conversation_metrics": {"metrics": {}},
        }
        recalculate_overall_status(trace)
        mock_apply.assert_called_once_with(trace, Execution.ERROR, None)

    @patch("rhesis.backend.app.services.annotation_override.trace._apply_outcome")
    def test_failed_turn_override_sets_fail(self, mock_apply):
        trace = MagicMock()
        trace.trace_metrics = {
            "turn_metrics": {
                "metrics": {
                    "m1": {"is_successful": True},
                    "m2": {"is_successful": True},
                }
            },
            "conversation_metrics": {"metrics": {}},
            "turn_overrides": {
                "2": {"success": False, "override": {"original_value": True, "annotation_id": "r1"}},
            },
        }
        recalculate_overall_status(trace)
        mock_apply.assert_called_once_with(trace, Execution.OK, Verdict.FAIL)

    @patch("rhesis.backend.app.services.annotation_override.trace._apply_outcome")
    def test_reviewed_crashed_metric_can_leave_error(self, mock_apply):
        trace = MagicMock()
        trace.trace_metrics = {
            "turn_metrics": {
                "metrics": {
                    "m1": {"is_successful": False, "error": "judge timed out"},
                }
            },
            "conversation_metrics": {"metrics": {}},
        }

        _apply_metric_override(
            trace, "m1", True, "review-1", "user-1", "2026-01-01T00:00:00+00:00"
        )

        metric = trace.trace_metrics["turn_metrics"]["metrics"]["m1"]
        assert "error" not in metric
        assert metric["override"]["original_error"] == "judge timed out"

        recalculate_overall_status(trace)
        mock_apply.assert_called_once_with(trace, Execution.OK, Verdict.PASS)
