"""Tests for effective metric success in stats aggregation."""

from rhesis.backend.app.constants import OverallTestResult
from rhesis.backend.app.services.stats.common import (
    automated_metric_success,
    effective_metric_success,
)


class TestAutomatedMetricSuccess:
    def test_uses_is_successful_without_override(self):
        assert automated_metric_success({"is_successful": True}) is True
        assert automated_metric_success({"is_successful": False}) is False

    def test_uses_original_value_when_override_present(self):
        data = {
            "is_successful": True,
            "override": {"original_value": False},
        }
        assert automated_metric_success(data) is False


class TestEffectiveMetricSuccess:
    def test_uses_automated_value_when_no_review(self):
        assert (
            effective_metric_success(OverallTestResult.FAILED, False, False) is False
        )
        assert effective_metric_success(OverallTestResult.PASSED, True, False) is True

    def test_metric_override_is_authoritative(self):
        assert effective_metric_success(OverallTestResult.FAILED, True, True) is True
        assert effective_metric_success(OverallTestResult.PASSED, False, True) is False

    def test_test_level_pass_review_overrides_failed_metric(self):
        assert (
            effective_metric_success(OverallTestResult.PASSED, False, False) is True
        )

    def test_test_level_fail_review_overrides_passing_metric(self):
        assert (
            effective_metric_success(OverallTestResult.FAILED, True, False) is False
        )

    def test_pending_result_uses_automated_metric(self):
        assert (
            effective_metric_success(OverallTestResult.PENDING, False, False) is False
        )
