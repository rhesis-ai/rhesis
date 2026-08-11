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
