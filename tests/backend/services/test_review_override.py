"""Unit tests for test-result review override metric key resolution."""

from unittest.mock import patch

from rhesis.backend.app.services.review_override import (
    _apply_metric_override,
    _find_metric_key,
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
            test_metrics = {
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
