"""Tests for mode='behavior_detail' per-behavior aggregation."""

from types import SimpleNamespace
from unittest.mock import patch

from rhesis.backend.app.constants import OverallTestResult
from rhesis.backend.app.models.stats_views import TestResultStatsView as V
from rhesis.backend.app.services.stats.test_result import (
    _behavior_breakdown,
    _behavior_dimensional_stats,
    _behavior_metric_stats,
    _behavior_overall_stats,
)


class _GroupedRowsQueryStub:
    """Mimics with_entities(...).group_by(...).all() returning already-aggregated rows."""

    def __init__(self, rows):
        self._rows = rows

    def with_entities(self, *_args):
        return self

    def group_by(self, *_args):
        return self

    def all(self):
        return self._rows


class _MetricRowsQueryStub:
    def __init__(self, rows):
        self._rows = rows

    def with_entities(self, *_args):
        return self

    def all(self):
        return self._rows


class TestBehaviorOverallStats:
    def test_groups_by_behavior_id_and_computes_pass_rate(self):
        rows = [
            SimpleNamespace(behavior_id="b1", passed=3, failed=1),
            SimpleNamespace(behavior_id="b2", passed=0, failed=2),
        ]

        stats = _behavior_overall_stats(_GroupedRowsQueryStub(rows))

        assert stats["b1"] == {"total": 4, "passed": 3, "failed": 1, "pass_rate": 75.0}
        assert stats["b2"] == {"total": 2, "passed": 0, "failed": 2, "pass_rate": 0.0}

    def test_null_behavior_id_is_skipped(self):
        rows = [SimpleNamespace(behavior_id=None, passed=1, failed=0)]

        assert _behavior_overall_stats(_GroupedRowsQueryStub(rows)) == {}

    def test_zero_total_has_zero_pass_rate(self):
        rows = [SimpleNamespace(behavior_id="b1", passed=0, failed=0)]

        assert _behavior_overall_stats(_GroupedRowsQueryStub(rows))["b1"]["pass_rate"] == 0


class TestBehaviorDimensionalStats:
    def test_groups_by_behavior_and_name(self):
        rows = [
            SimpleNamespace(behavior_id="b1", name="Healthcare", passed=1, failed=0),
            SimpleNamespace(behavior_id="b1", name="Finance", passed=0, failed=1),
            SimpleNamespace(behavior_id="b2", name="Healthcare", passed=2, failed=0),
        ]

        stats = _behavior_dimensional_stats(_GroupedRowsQueryStub(rows), name_col=V.topic_name)

        assert set(stats["b1"].keys()) == {"Healthcare", "Finance"}
        assert stats["b1"]["Healthcare"]["pass_rate"] == 100.0
        assert stats["b2"]["Healthcare"] == {
            "total": 2,
            "passed": 2,
            "failed": 0,
            "pass_rate": 100.0,
        }

    def test_null_name_falls_back_to_unknown(self):
        rows = [SimpleNamespace(behavior_id="b1", name=None, passed=1, failed=0)]

        stats = _behavior_dimensional_stats(_GroupedRowsQueryStub(rows), name_col=V.topic_name)

        assert "Unknown" in stats["b1"]

    def test_null_behavior_id_is_skipped(self):
        rows = [SimpleNamespace(behavior_id=None, name="Healthcare", passed=1, failed=0)]

        assert _behavior_dimensional_stats(_GroupedRowsQueryStub(rows), name_col=V.topic_name) == {}


class TestBehaviorMetricStats:
    def test_splits_metric_stats_per_behavior(self):
        rows = [
            (
                "b1",
                {"metrics": {"Accuracy": {"is_successful": True}}},
                OverallTestResult.PASSED,
            ),
            (
                "b2",
                {"metrics": {"Accuracy": {"is_successful": False}}},
                OverallTestResult.FAILED,
            ),
        ]

        stats = _behavior_metric_stats(_MetricRowsQueryStub(rows))

        assert stats["b1"]["Accuracy"]["passed"] == 1
        assert stats["b2"]["Accuracy"]["failed"] == 1
        assert "Accuracy" not in stats.get("b3", {})

    def test_null_behavior_id_is_skipped(self):
        rows = [
            (None, {"metrics": {"Accuracy": {"is_successful": True}}}, OverallTestResult.PASSED)
        ]

        assert _behavior_metric_stats(_MetricRowsQueryStub(rows)) == {}

    def test_metric_override_uses_original_value_for_automated_counts(self):
        rows = [
            (
                "b1",
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

        stats = _behavior_metric_stats(_MetricRowsQueryStub(rows))

        assert stats["b1"]["Accuracy"]["automated_passed"] == 0
        assert stats["b1"]["Accuracy"]["human_review_count"] == 1


class TestBehaviorBreakdown:
    def test_merges_behavior_ids_present_in_any_sub_result(self):
        with (
            patch(
                "rhesis.backend.app.services.stats.test_result._behavior_overall_stats",
                return_value={"b1": {"total": 2, "passed": 2, "failed": 0, "pass_rate": 100.0}},
            ),
            patch(
                "rhesis.backend.app.services.stats.test_result._behavior_metric_stats",
                return_value={"b2": {"Accuracy": {"total": 1}}},
            ),
            patch(
                "rhesis.backend.app.services.stats.test_result._behavior_dimensional_stats",
                return_value={"b3": {"Healthcare": {"total": 1}}},
            ),
        ):
            result = _behavior_breakdown(base_q=None)

        assert set(result.keys()) == {"b1", "b2", "b3"}
        assert result["b1"]["overall_pass_rates"]["passed"] == 2
        assert result["b1"]["metric_pass_rates"] == {}
        assert result["b1"]["topic_pass_rates"] == {}

        assert result["b2"]["overall_pass_rates"] == {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0,
        }
        assert result["b2"]["metric_pass_rates"] == {"Accuracy": {"total": 1}}

        assert result["b3"]["topic_pass_rates"] == {"Healthcare": {"total": 1}}
