"""Tests for get_test_statistics/get_test_statistics_for_runs -- grouped by
test_result.execution/verdict (the outcome-model source of truth, see
app/outcomes.py) rather than the legacy status name and its synonym lists.
"""

from uuid import uuid4

import pytest

from rhesis.backend.app import models
from rhesis.backend.jobs.execution.result_processor import (
    get_test_statistics,
    get_test_statistics_for_runs,
)


def _result(db, test_run, test_config, org_id, user_id, execution, verdict):
    result = models.TestResult(
        test_run_id=test_run.id,
        test_configuration_id=test_config.id,
        organization_id=org_id,
        user_id=user_id,
        execution=execution,
        verdict=verdict,
    )
    db.add(result)
    return result


@pytest.mark.unit
class TestGetTestStatistics:
    def test_counts_pass_fail_error_by_execution_verdict(
        self, test_db, test_organization, db_user, db_test_configuration, db_test_run
    ):
        org_id = test_organization.id
        user_id = db_user.id

        for execution, verdict in [
            ("ok", "pass"),
            ("ok", "pass"),
            ("ok", "fail"),
            ("error", None),
            # cancelled buckets with error here -- get_test_statistics has
            # no separate "cancelled" return value.
            ("cancelled", None),
        ]:
            _result(
                test_db, db_test_run, db_test_configuration, org_id, user_id, execution, verdict
            )
        test_db.commit()

        total, passed, failed, errors = get_test_statistics(db_test_run, test_db)

        assert total == 5
        assert passed == 2
        assert failed == 1
        assert errors == 2

    def test_inconclusive_and_not_run_count_toward_total_but_no_bucket(
        self, test_db, test_organization, db_user, db_test_configuration, db_test_run
    ):
        """Bug this migration fixes: the old status-name classifier had no
        branch for "Inconclusive" and silently counted it as an execution
        error. It must now fall into none of the three buckets while still
        counting toward the total.
        """
        org_id = test_organization.id
        user_id = db_user.id

        _result(test_db, db_test_run, db_test_configuration, org_id, user_id, "ok", "inconclusive")
        _result(test_db, db_test_run, db_test_configuration, org_id, user_id, "not_run", None)
        test_db.commit()

        total, passed, failed, errors = get_test_statistics(db_test_run, test_db)

        assert total == 2
        assert passed == 0
        assert failed == 0
        assert errors == 0


@pytest.mark.unit
class TestGetTestStatisticsForRuns:
    def test_aggregates_per_run(
        self, test_db, test_organization, db_user, db_test_configuration, db_test_run
    ):
        org_id = test_organization.id
        user_id = db_user.id

        for execution, verdict in [("ok", "pass"), ("ok", "fail"), ("error", None)]:
            _result(
                test_db, db_test_run, db_test_configuration, org_id, user_id, execution, verdict
            )
        test_db.commit()

        stats = get_test_statistics_for_runs(test_db, [db_test_run.id])

        assert stats[str(db_test_run.id)] == {"total": 3, "passed": 1, "failed": 1, "errors": 1}

    def test_run_with_no_results_gets_zero_bucket(self, test_db):
        run_id = uuid4()

        stats = get_test_statistics_for_runs(test_db, [run_id])

        assert stats[str(run_id)] == {"total": 0, "passed": 0, "failed": 0, "errors": 0}
