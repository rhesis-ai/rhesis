"""create_test_run's metric-plan snapshot is best-effort and must not be
able to take the dispatch down with it.

The snapshot runs several queries on the caller's session. A DB error in any
of them aborts the surrounding transaction, so swallowing the exception
without rolling back would leave create_test_run's own INSERT to fail with
InFailedSqlTransaction -- turning a skippable nicety into a 500 on every
run dispatch.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.jobs.execution.run import create_test_run


@pytest.fixture
def dispatch_setup(test_db: Session, test_organization, db_user, db_endpoint, db_status):
    test_config = models.TestConfiguration(
        endpoint_id=db_endpoint.id,
        organization_id=test_organization.id,
        user_id=db_user.id,
    )
    test_db.add(test_config)
    test_db.flush()

    test_set = models.TestSet(
        name="Dispatch Test Set",
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
    )
    test_db.add(test_set)
    test_db.flush()
    test_config.test_set_id = test_set.id

    test = models.Test(
        user_id=db_user.id, organization_id=test_organization.id, requirement_id=None
    )
    test_db.add(test)
    test_db.flush()
    test_db.execute(
        models.test_test_set_association.insert().values(
            test_id=test.id,
            test_set_id=test_set.id,
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
    )
    test_db.commit()
    return test_config


class TestMetricPlanSnapshotIsBestEffort:
    def test_plan_is_stored_on_the_run(self, test_db: Session, dispatch_setup):
        test_run = create_test_run(test_db, dispatch_setup)
        test_db.commit()

        assert "metric_plan" in (test_run.attributes or {})
        assert test_run.attributes["metric_plan"]["test_order"]

    def test_database_error_in_the_plan_does_not_fail_dispatch(
        self, test_db: Session, dispatch_setup
    ):
        """A DB error inside the snapshot must leave the session usable, so
        the run row still gets created and committed.

        The failure has to be real SQL, not a mocked Python exception:
        Postgres marks the whole transaction aborted, and it is that state
        -- not the exception -- that the SAVEPOINT exists to contain. A
        raise-only mock leaves the transaction healthy and the test passes
        with or without the fix.
        """

        def _boom(db, *args, **kwargs):
            db.execute(text("SELECT * FROM a_table_that_does_not_exist"))

        with patch(
            "rhesis.backend.jobs.execution.metric_plan._build_metric_plan",
            side_effect=_boom,
        ):
            test_run = create_test_run(test_db, dispatch_setup)
            # The commit is the assertion: an aborted transaction raises here.
            test_db.commit()

        assert test_run.id is not None
        assert "metric_plan" not in (test_run.attributes or {})

    def test_plan_failure_leaves_the_run_readable(self, test_db: Session, dispatch_setup):
        """And the run is a real row afterwards, not a half-flushed object."""

        with patch(
            "rhesis.backend.jobs.execution.metric_plan._build_metric_plan",
            side_effect=ValueError("planner bug"),
        ):
            test_run = create_test_run(test_db, dispatch_setup)
            test_db.commit()

        reloaded = test_db.query(models.TestRun).filter(models.TestRun.id == test_run.id).first()
        assert reloaded is not None
        assert "metric_plan" not in (reloaded.attributes or {})
