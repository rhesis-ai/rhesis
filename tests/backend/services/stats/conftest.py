"""Shared DB fixtures for stats aggregation tests.

These build real Status/Test/TestResult rows so aggregation functions run
their actual SQL GROUP BY queries against v_test_result_stats/v_metric_stats,
rather than being exercised through a query-object stub.
"""

import pytest

from rhesis.backend.app import models


@pytest.fixture
def passed_status(test_db, test_organization, db_user, test_type_lookup):
    status = models.Status(
        name="Passed",
        entity_type_id=test_type_lookup.id,
        organization_id=test_organization.id,
        user_id=db_user.id,
    )
    test_db.add(status)
    test_db.flush()
    return status


@pytest.fixture
def failed_status(test_db, test_organization, db_user, test_type_lookup):
    status = models.Status(
        name="Failed",
        entity_type_id=test_type_lookup.id,
        organization_id=test_organization.id,
        user_id=db_user.id,
    )
    test_db.add(status)
    test_db.flush()
    return status


@pytest.fixture
def db_behavior(test_db, test_organization, db_user):
    behavior = models.Behavior(
        name="Toxicity",
        organization_id=test_organization.id,
        user_id=db_user.id,
    )
    test_db.add(behavior)
    test_db.flush()
    return behavior


@pytest.fixture
def db_behavior_2(test_db, test_organization, db_user):
    behavior = models.Behavior(
        name="Bias",
        organization_id=test_organization.id,
        user_id=db_user.id,
    )
    test_db.add(behavior)
    test_db.flush()
    return behavior


@pytest.fixture
def make_test_result(test_db, test_organization, db_user, db_test_configuration, db_test_run):
    """Factory creating a Test + TestResult pair backed by real DB rows.

    Returns the TestResult; pass behavior_id to exercise per-behavior grouping.
    """

    def _make(status, test_metrics, behavior_id=None):
        test = models.Test(
            priority=1,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=status.id,
            behavior_id=behavior_id,
        )
        test_db.add(test)
        test_db.flush()

        result = models.TestResult(
            test_id=test.id,
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=status.id,
            test_metrics=test_metrics,
        )
        test_db.add(result)
        test_db.flush()
        return result

    return _make


@pytest.fixture
def base_q(test_db, db_test_run):
    """A base_q scoped to this test's own test_run, matching how
    get_test_result_stats builds it via _apply_filters in production."""
    from rhesis.backend.app.models.stats_views import TestResultStatsView as V

    return test_db.query(V).filter(V.test_run_id == db_test_run.id)
