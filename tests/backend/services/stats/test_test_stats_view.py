"""Tests for v_test_stats -- verifies unrun tests surface correctly.

Unlike v_test_result_stats/v_metric_stats (anchored on test_result, so a test
with zero results is structurally invisible), v_test_stats is anchored on
test and LEFT JOINs an aggregate of its test_result rows. These exercise that
against real Test/TestResult rows.
"""

from rhesis.backend.app import models
from rhesis.backend.app.models.stats_views import TestStatsView


class TestTestStatsView:
    def test_test_with_no_results_is_unrun(
        self, test_db, test_organization, db_user, passed_status
    ):
        test = models.Test(
            priority=1,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=passed_status.id,
        )
        test_db.add(test)
        test_db.flush()

        row = test_db.query(TestStatsView).filter(TestStatsView.test_id == test.id).one()

        assert row.run_count == 0
        assert row.passed_count == 0
        assert row.failed_count == 0
        assert row.pending_count == 0
        assert row.is_unrun is True
        assert row.last_run_at is None

    def test_test_with_results_aggregates_pass_fail_counts(
        self,
        test_db,
        test_organization,
        db_user,
        db_test_configuration,
        db_test_run,
        passed_status,
        failed_status,
    ):
        test = models.Test(
            priority=1,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=passed_status.id,
        )
        test_db.add(test)
        test_db.flush()

        for status in (passed_status, failed_status):
            result = models.TestResult(
                test_id=test.id,
                test_run_id=db_test_run.id,
                test_configuration_id=db_test_configuration.id,
                user_id=db_user.id,
                organization_id=test_organization.id,
                status_id=status.id,
                test_metrics={},
            )
            test_db.add(result)
        test_db.flush()

        row = test_db.query(TestStatsView).filter(TestStatsView.test_id == test.id).one()

        assert row.run_count == 2
        assert row.passed_count == 1
        assert row.failed_count == 1
        assert row.pending_count == 0
        assert row.is_unrun is False
        assert row.last_run_at is not None
