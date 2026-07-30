"""Tests for mode='ids' test_id resolution (metric-scoped and overall).

_test_ids_by_metric now filters v_metric_stats directly via SQL, so its
tests use real Test/TestResult rows. _test_ids_overall is unchanged (still
a plain distinct() filter on v_test_result_stats) and keeps its query stub.
"""

from types import SimpleNamespace

from rhesis.backend.app.constants import OverallTestResult
from rhesis.backend.app.services.stats.test_result import (
    _test_ids_by_metric,
    _test_ids_overall,
)


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
    def test_matches_metric_pass_outcome(self, test_db, base_q, make_test_result, passed_status,
                                          failed_status):
        r1 = make_test_result(passed_status, {"metrics": {"Accuracy": {"is_successful": True}}})
        r2 = make_test_result(failed_status, {"metrics": {"Accuracy": {"is_successful": False}}})

        assert _test_ids_by_metric(test_db, base_q, "Accuracy", "pass") == [r1.test_id]
        assert _test_ids_by_metric(test_db, base_q, "Accuracy", "fail") == [r2.test_id]

    def test_outcome_all_ignores_success_value(self, test_db, base_q, make_test_result,
                                                passed_status, failed_status):
        r1 = make_test_result(passed_status, {"metrics": {"Accuracy": {"is_successful": True}}})
        r2 = make_test_result(failed_status, {"metrics": {"Accuracy": {"is_successful": False}}})

        assert set(_test_ids_by_metric(test_db, base_q, "Accuracy", "all")) == {
            r1.test_id,
            r2.test_id,
        }

    def test_metric_override_uses_effective_success(self, test_db, base_q, make_test_result,
                                                      failed_status):
        r1 = make_test_result(
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

        assert _test_ids_by_metric(test_db, base_q, "Accuracy", "pass") == [r1.test_id]
        assert _test_ids_by_metric(test_db, base_q, "Accuracy", "fail") == []

    def test_rows_missing_requested_metric_are_skipped(self, test_db, base_q, make_test_result,
                                                         passed_status):
        make_test_result(passed_status, {"metrics": {"Other": {"is_successful": True}}})

        assert _test_ids_by_metric(test_db, base_q, "Accuracy", "all") == []

    def test_rows_without_test_metrics_are_skipped(self, test_db, base_q, make_test_result,
                                                    passed_status):
        make_test_result(passed_status, None)
        make_test_result(passed_status, {})

        assert _test_ids_by_metric(test_db, base_q, "Accuracy", "all") == []

    def test_duplicate_test_id_rows_deduplicate(self, test_db, base_q, make_test_result,
                                                 passed_status, test_organization, db_user,
                                                 db_test_run, db_test_configuration):
        from rhesis.backend.app import models

        r1 = make_test_result(passed_status, {"metrics": {"Accuracy": {"is_successful": True}}})
        # A second run of the same test -- same test_id, different test_result row.
        r2 = models.TestResult(
            test_id=r1.test_id,
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=passed_status.id,
            test_metrics={"metrics": {"Accuracy": {"is_successful": True}}},
        )
        test_db.add(r2)
        test_db.flush()

        assert _test_ids_by_metric(test_db, base_q, "Accuracy", "all") == [r1.test_id]


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
