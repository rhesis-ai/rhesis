"""Tests for v_metric_stats -- verifies each metric is counted by its own outcome.

effective_success previously fell back to the test's overall Pass/Fail whenever it
disagreed with a metric's own is_successful. That overall status is itself an AND
across all of a test's metrics, so on any test with mixed metric outcomes it
disagreed with the passing metrics by construction -- one failing metric dragged
every other (actually-passing) metric on that same test into "failed" in the
aggregate stats. These exercise the real view against Test/TestResult rows to
confirm that no longer happens.
"""

from rhesis.backend.app import models
from rhesis.backend.app.models.stats_views import MetricStatsView


def _rows_by_metric(test_db, test_result_id):
    rows = (
        test_db.query(MetricStatsView)
        .filter(MetricStatsView.test_result_id == test_result_id)
        .all()
    )
    return {row.metric_name: row for row in rows}


class TestMetricStatsView:
    def test_one_failing_metric_does_not_fail_the_others_on_the_same_test(
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

        result = models.TestResult(
            test_id=test.id,
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=failed_status.id,
            test_metrics={
                "metrics": {
                    "Answer Relevancy": {"is_successful": True},
                    "Faithfulness": {"is_successful": False},
                    "Contextual Precision": {"is_successful": True},
                }
            },
        )
        test_db.add(result)
        test_db.flush()

        by_metric = _rows_by_metric(test_db, result.id)

        assert by_metric["Answer Relevancy"].effective_success is True
        assert by_metric["Faithfulness"].effective_success is False
        assert by_metric["Contextual Precision"].effective_success is True

    def test_metric_level_override_is_authoritative_for_that_metric(
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

        result = models.TestResult(
            test_id=test.id,
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=passed_status.id,
            test_metrics={
                "metrics": {
                    "Faithfulness": {
                        "is_successful": True,
                        "override": {"original_value": False},
                    }
                }
            },
        )
        test_db.add(result)
        test_db.flush()

        row = _rows_by_metric(test_db, result.id)["Faithfulness"]

        assert row.has_override is True
        assert row.automated_success is False
        assert row.effective_success is True
