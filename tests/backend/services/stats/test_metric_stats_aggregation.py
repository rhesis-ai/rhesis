"""Tests for metric pass-rate aggregation with human reviews."""

from rhesis.backend.app.constants import OverallTestResult
from rhesis.backend.app.services.stats.test_result import _metric_stats


class _Row:
    def __init__(self, test_metrics, result):
        self.test_metrics = test_metrics
        self.result = result


class _QueryStub:
    def __init__(self, rows):
        self._rows = rows

    def with_entities(self, *_args):
        return self

    def all(self):
        return self._rows


class TestMetricStatsAggregation:
    def test_metric_override_uses_original_value_for_automated_counts(self):
        rows = [
            _Row(
                {
                    "metrics": {
                        "Accuracy": {
                            "is_successful": True,
                            "override": {"original_value": False},
                        }
                    }
                },
                OverallTestResult.FAILED,
            )
        ]

        stats = _metric_stats(_QueryStub(rows))

        assert stats["Accuracy"] == {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 100.0,
            "automated_passed": 0,
            "automated_failed": 1,
            "human_review_count": 1,
        }

    def test_test_level_review_without_metric_override(self):
        rows = [
            _Row(
                {"metrics": {"Accuracy": {"is_successful": False}}},
                OverallTestResult.PASSED,
            )
        ]

        stats = _metric_stats(_QueryStub(rows))

        assert stats["Accuracy"]["passed"] == 1
        assert stats["Accuracy"]["automated_passed"] == 0
        assert stats["Accuracy"]["human_review_count"] == 1
