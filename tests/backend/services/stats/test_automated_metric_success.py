"""Tests for the pre-review automated metric outcome helper."""

from rhesis.backend.app.services.stats.common import automated_metric_success


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
