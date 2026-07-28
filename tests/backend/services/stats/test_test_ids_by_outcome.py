"""Tests for mode='ids' test_id resolution (metric-scoped and overall)."""

from types import SimpleNamespace

from rhesis.backend.app.constants import OverallTestResult
from rhesis.backend.app.services.stats.test_result import (
    _test_ids_by_metric,
    _test_ids_overall,
)


class _MetricRowsQueryStub:
    def __init__(self, rows):
        # rows: list of (test_id, test_metrics, result) tuples matching SQLAlchemy .all()
        self._rows = rows

    def with_entities(self, *_args):
        return self

    def all(self):
        return self._rows


class _OverallQueryStub:
    """Mimics with_entities(...).distinct().filter(...).all(), where filter()
    narrows the underlying rows (WHERE semantics) and distinct() dedups the
    projected column regardless of call order (matches real SQL semantics)."""

    def __init__(self, rows):
        self._rows = rows
        self._distinct = False

    def with_entities(self, *_args):
        return self

    def distinct(self):
        self._distinct = True
        return self

    def filter(self, cond):
        value = cond.right.value
        self._rows = [r for r in self._rows if r.result == value]
        return self

    def all(self):
        if not self._distinct:
            return self._rows
        seen = set()
        deduped = []
        for r in self._rows:
            if r.test_id in seen:
                continue
            seen.add(r.test_id)
            deduped.append(r)
        return deduped


class TestTestIdsByMetric:
    def test_matches_metric_pass_outcome(self):
        rows = [
            ("t1", {"metrics": {"Accuracy": {"is_successful": True}}}, OverallTestResult.PASSED),
            ("t2", {"metrics": {"Accuracy": {"is_successful": False}}}, OverallTestResult.FAILED),
        ]

        assert _test_ids_by_metric(_MetricRowsQueryStub(rows), "Accuracy", "pass") == ["t1"]
        assert _test_ids_by_metric(_MetricRowsQueryStub(rows), "Accuracy", "fail") == ["t2"]

    def test_outcome_all_ignores_success_value(self):
        rows = [
            ("t1", {"metrics": {"Accuracy": {"is_successful": True}}}, OverallTestResult.PASSED),
            ("t2", {"metrics": {"Accuracy": {"is_successful": False}}}, OverallTestResult.FAILED),
        ]

        assert set(_test_ids_by_metric(_MetricRowsQueryStub(rows), "Accuracy", "all")) == {
            "t1",
            "t2",
        }

    def test_metric_override_uses_effective_success(self):
        rows = [
            (
                "t1",
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

        assert _test_ids_by_metric(_MetricRowsQueryStub(rows), "Accuracy", "pass") == ["t1"]
        assert _test_ids_by_metric(_MetricRowsQueryStub(rows), "Accuracy", "fail") == []

    def test_rows_missing_requested_metric_are_skipped(self):
        rows = [("t1", {"metrics": {"Other": {"is_successful": True}}}, OverallTestResult.PASSED)]

        assert _test_ids_by_metric(_MetricRowsQueryStub(rows), "Accuracy", "all") == []

    def test_rows_without_test_metrics_are_skipped(self):
        rows = [("t1", None, OverallTestResult.PASSED), ("t2", {}, OverallTestResult.PASSED)]

        assert _test_ids_by_metric(_MetricRowsQueryStub(rows), "Accuracy", "all") == []

    def test_duplicate_test_id_rows_deduplicate(self):
        rows = [
            ("t1", {"metrics": {"Accuracy": {"is_successful": True}}}, OverallTestResult.PASSED),
            ("t1", {"metrics": {"Accuracy": {"is_successful": True}}}, OverallTestResult.PASSED),
        ]

        assert _test_ids_by_metric(_MetricRowsQueryStub(rows), "Accuracy", "all") == ["t1"]


class TestTestIdsOverall:
    def test_outcome_all_returns_deduplicated_ids(self):
        rows = [
            SimpleNamespace(test_id="t1", result=OverallTestResult.PASSED),
            SimpleNamespace(test_id="t1", result=OverallTestResult.FAILED),
            SimpleNamespace(test_id="t2", result=OverallTestResult.FAILED),
        ]

        assert set(_test_ids_overall(_OverallQueryStub(rows), "all")) == {"t1", "t2"}

    def test_outcome_pass_includes_test_with_any_passed_run(self):
        rows = [
            SimpleNamespace(test_id="t1", result=OverallTestResult.PASSED),
            SimpleNamespace(test_id="t1", result=OverallTestResult.FAILED),
            SimpleNamespace(test_id="t2", result=OverallTestResult.FAILED),
        ]

        assert _test_ids_overall(_OverallQueryStub(rows), "pass") == ["t1"]

    def test_outcome_fail_excludes_tests_without_a_failed_run(self):
        rows = [
            SimpleNamespace(test_id="t1", result=OverallTestResult.PASSED),
            SimpleNamespace(test_id="t2", result=OverallTestResult.FAILED),
        ]

        assert _test_ids_overall(_OverallQueryStub(rows), "fail") == ["t2"]
