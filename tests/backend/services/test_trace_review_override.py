"""
Unit tests for rhesis.backend.app.services.trace_review_override

Tests the apply/revert/recalculate logic for human review overrides
on trace_metrics JSONB data.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.services.trace_review_override import (
    _apply_metric_override,
    _find_metric_in_trace_metrics,
    _get_all_trace_metric_values,
    _is_passed_status,
    _revert_metric_override,
    apply_review_override,
    recalculate_overall_status,
    revert_override,
)


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


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "user-456"
    user.name = "Test User"
    user.email = "test@example.com"
    return user


class TestIsPassedStatus:
    def test_pass_is_passed(self):
        assert _is_passed_status("Pass") is True

    def test_fail_is_not_passed(self):
        assert _is_passed_status("Fail") is False

    def test_error_is_not_passed(self):
        assert _is_passed_status("Error") is False

    def test_empty_string_is_not_passed(self):
        assert _is_passed_status("") is False


class TestFindMetricInTraceMetrics:
    def test_find_in_turn_metrics(self, mock_trace):
        result = _find_metric_in_trace_metrics(mock_trace.trace_metrics, "faithfulness")
        assert result is not None
        assert result["score"] == 0.9

    def test_find_in_conversation_metrics(self, mock_trace):
        result = _find_metric_in_trace_metrics(mock_trace.trace_metrics, "coherence")
        assert result is not None
        assert result["score"] == 0.95

    def test_not_found(self, mock_trace):
        result = _find_metric_in_trace_metrics(mock_trace.trace_metrics, "nonexistent")
        assert result is None

    def test_empty_trace_metrics(self):
        assert _find_metric_in_trace_metrics({}, "anything") is None


class TestGetAllTraceMetricValues:
    def test_collects_all_metrics(self, mock_trace):
        result = _get_all_trace_metric_values(mock_trace.trace_metrics)
        assert len(result) == 3

    def test_empty_trace_metrics(self):
        assert _get_all_trace_metric_values({}) == []

    def test_only_turn_metrics(self):
        data = {"turn_metrics": {"metrics": {"m1": {"is_successful": True}}}}
        result = _get_all_trace_metric_values(data)
        assert len(result) == 1

    def test_skips_non_dict_values(self):
        data = {"turn_metrics": {"metrics": {"bad": "not a dict", "good": {"is_successful": True}}}}
        result = _get_all_trace_metric_values(data)
        assert len(result) == 1


class TestApplyMetricOverride:
    def test_override_changes_is_successful(self, mock_trace, mock_user):
        _apply_metric_override(mock_trace, "relevance", True, "rev-1", mock_user, "now")

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["relevance"]
        assert metric["is_successful"] is True
        assert "override" in metric
        assert metric["override"]["original_value"] is False
        assert metric["override"]["review_id"] == "rev-1"

    def test_override_removes_when_matching_original(self, mock_trace, mock_user):
        _apply_metric_override(mock_trace, "faithfulness", True, "rev-1", mock_user, "now")

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["faithfulness"]
        assert metric["is_successful"] is True
        assert "override" not in metric

    def test_override_preserves_original_on_second_override(self, mock_trace, mock_user):
        _apply_metric_override(mock_trace, "relevance", True, "rev-1", mock_user, "t1")

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["relevance"]
        assert metric["override"]["original_value"] is False

        _apply_metric_override(mock_trace, "relevance", False, "rev-2", mock_user, "t2")
        assert metric["is_successful"] is False
        assert "override" not in metric

    def test_no_op_on_empty_trace_metrics(self, mock_user):
        trace = MagicMock()
        trace.trace_metrics = None
        _apply_metric_override(trace, "anything", True, "rev-1", mock_user, "now")

    def test_no_op_on_missing_metric(self, mock_trace, mock_user):
        _apply_metric_override(mock_trace, "nonexistent", True, "rev-1", mock_user, "now")
        assert "nonexistent" not in mock_trace.trace_metrics["turn_metrics"]["metrics"]


class TestApplyReviewOverride:
    @patch("rhesis.backend.app.services.trace_review_override._set_trace_status")
    def test_trace_target_sets_status(self, mock_set_status, mock_trace, mock_user):
        apply_review_override(
            mock_trace, "trace", None, {"name": "Pass"}, mock_user, "rev-1"
        )
        mock_set_status.assert_called_once_with(mock_trace, True)

    @patch("rhesis.backend.app.services.trace_review_override.recalculate_overall_status")
    def test_metric_target_overrides_and_recalculates(
        self, mock_recalc, mock_trace, mock_user
    ):
        apply_review_override(
            mock_trace, "metric", "relevance", {"name": "Pass"}, mock_user, "rev-1"
        )

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["relevance"]
        assert metric["is_successful"] is True
        mock_recalc.assert_called_once_with(mock_trace)


class TestRevertMetricOverride:
    def test_revert_restores_original(self, mock_trace, mock_user):
        _apply_metric_override(mock_trace, "relevance", True, "rev-1", mock_user, "now")

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["relevance"]
        assert metric["is_successful"] is True
        assert metric["override"]["review_id"] == "rev-1"

        _revert_metric_override(mock_trace, "relevance", "rev-1", None)

        assert metric["is_successful"] is False
        assert "override" not in metric

    def test_revert_applies_replacement_review(self, mock_trace, mock_user):
        _apply_metric_override(mock_trace, "relevance", True, "rev-1", mock_user, "now")

        replacement = {
            "review_id": "rev-2",
            "status": {"name": "Pass"},
            "user": {"user_id": "user-789"},
        }
        _revert_metric_override(mock_trace, "relevance", "rev-1", replacement)

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["relevance"]
        assert metric["is_successful"] is True
        assert metric["override"]["review_id"] == "rev-2"

    def test_revert_skips_if_different_review_id(self, mock_trace, mock_user):
        _apply_metric_override(mock_trace, "relevance", True, "rev-1", mock_user, "now")

        _revert_metric_override(mock_trace, "relevance", "rev-other", None)

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["relevance"]
        assert metric["is_successful"] is True
        assert metric["override"]["review_id"] == "rev-1"

    def test_revert_replacement_matches_original_clears_override(
        self, mock_trace, mock_user
    ):
        _apply_metric_override(mock_trace, "relevance", True, "rev-1", mock_user, "now")

        replacement = {
            "review_id": "rev-2",
            "status": {"name": "Fail"},
            "user": {"user_id": "user-789"},
        }
        _revert_metric_override(mock_trace, "relevance", "rev-1", replacement)

        metric = mock_trace.trace_metrics["turn_metrics"]["metrics"]["relevance"]
        assert metric["is_successful"] is False
        assert "override" not in metric


class TestRevertOverride:
    @patch("rhesis.backend.app.services.trace_review_override.recalculate_overall_status")
    @patch("rhesis.backend.app.services.trace_review_override._set_trace_status")
    def test_revert_trace_with_remaining_reviews(
        self, mock_set_status, mock_recalc, mock_trace, mock_user
    ):
        remaining = [
            {
                "target": {"type": "trace"},
                "status": {"name": "Fail"},
                "updated_at": "2025-01-01T00:00:00",
            }
        ]
        revert_override(mock_trace, "trace", None, "rev-del", remaining)
        mock_set_status.assert_called_once_with(mock_trace, False)
        mock_recalc.assert_not_called()

    @patch("rhesis.backend.app.services.trace_review_override.recalculate_overall_status")
    @patch("rhesis.backend.app.services.trace_review_override._set_trace_status")
    def test_revert_trace_no_remaining_recalculates(
        self, mock_set_status, mock_recalc, mock_trace, mock_user
    ):
        revert_override(mock_trace, "trace", None, "rev-del", [])
        mock_set_status.assert_not_called()
        mock_recalc.assert_called_once_with(mock_trace)


class TestRecalculateOverallStatus:
    @patch("rhesis.backend.app.services.trace_review_override._set_trace_status")
    def test_all_passed_sets_pass(self, mock_set_status):
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
        mock_set_status.assert_called_once_with(trace, True)

    @patch("rhesis.backend.app.services.trace_review_override._set_trace_status")
    def test_one_failed_sets_fail(self, mock_set_status):
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
        mock_set_status.assert_called_once_with(trace, False)

    @patch("rhesis.backend.app.services.trace_review_override._set_trace_status")
    def test_no_metrics_no_op(self, mock_set_status):
        trace = MagicMock()
        trace.trace_metrics = {"turn_metrics": {"metrics": {}}, "conversation_metrics": {"metrics": {}}}
        recalculate_overall_status(trace)
        mock_set_status.assert_not_called()

    @patch("rhesis.backend.app.services.trace_review_override._set_trace_status")
    def test_none_trace_metrics_no_op(self, mock_set_status):
        trace = MagicMock()
        trace.trace_metrics = None
        recalculate_overall_status(trace)
        mock_set_status.assert_not_called()

    @patch("rhesis.backend.app.services.trace_review_override._set_trace_status")
    def test_failed_turn_override_sets_fail(self, mock_set_status):
        """Even if all metrics pass, a failed turn override should result in Fail."""
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
                "2": {"success": False, "override": {"original_value": True, "review_id": "r1"}},
            },
        }
        recalculate_overall_status(trace)
        mock_set_status.assert_called_once_with(trace, False)

    @patch("rhesis.backend.app.services.trace_review_override._set_trace_status")
    def test_all_pass_with_passing_turn_override(self, mock_set_status):
        """All metrics pass and turn overrides also pass -> overall Pass."""
        trace = MagicMock()
        trace.trace_metrics = {
            "turn_metrics": {
                "metrics": {"m1": {"is_successful": True}}
            },
            "conversation_metrics": {"metrics": {}},
            "turn_overrides": {
                "1": {"success": True, "override": {"original_value": False, "review_id": "r2"}},
            },
        }
        recalculate_overall_status(trace)
        mock_set_status.assert_called_once_with(trace, True)
