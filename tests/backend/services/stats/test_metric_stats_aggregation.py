"""Tests for metric pass-rate aggregation with human reviews.

_metric_stats runs a SQL GROUP BY on v_metric_stats, so these exercise it
against real Test/TestResult rows rather than a stubbed query object.
"""

from rhesis.backend.app.services.stats.test_result import _metric_stats


class TestMetricStatsAggregation:
    def test_metric_override_uses_original_value_for_automated_counts(
        self, test_db, base_q, make_test_result, failed_status
    ):
        make_test_result(
            failed_status,
            {
                "metrics": {
                    "Accuracy": {
                        "is_successful": True,
                        "override": {"original_value": False},
                    }
                }
            },
        )

        stats = _metric_stats(test_db, base_q)

        assert stats["Accuracy"] == {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 100.0,
            "automated_passed": 0,
            "automated_failed": 1,
            "human_review_count": 1,
        }

    def test_status_metric_mismatch_without_override_is_not_a_review(
        self, test_db, base_q, make_test_result, passed_status
    ):
        make_test_result(passed_status, {"metrics": {"Accuracy": {"is_successful": False}}})

        stats = _metric_stats(test_db, base_q)

        assert stats["Accuracy"]["passed"] == 1
        assert stats["Accuracy"]["automated_passed"] == 0
        assert stats["Accuracy"]["human_review_count"] == 0
