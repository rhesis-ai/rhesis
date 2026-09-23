"""`enforce_test_run_quota`: a run must fit in what's left after the runs
already queued or running, whose tests ``usage`` doesn't hold until they end."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from rhesis.backend.app.models.test import Test, test_test_set_association
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.quota import OveragePolicy, QuotaPolicy, QuotaRegistry, QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError
from rhesis.backend.app.services.test_set import IN_FLIGHT_RUN_WINDOW, enforce_test_run_quota
from rhesis.backend.app.services.usage import increment_usage
from rhesis.backend.app.utils.crud_utils import get_or_create_status


class _FixedPolicyProvider:
    def __init__(self, policy: QuotaPolicy):
        self._policy = policy

    def get_policy(self, org=None) -> QuotaPolicy:
        return self._policy


@pytest.fixture(autouse=True)
def hard_limit_of_10():
    saved_provider = QuotaRegistry._provider
    QuotaRegistry.reset()
    QuotaRegistry.set_quota_provider(
        _FixedPolicyProvider(
            QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 10}, overage=OveragePolicy.HARD)
        )
    )
    yield
    QuotaRegistry._provider = saved_provider


@pytest.fixture
def three_test_set(test_db, test_organization, db_user, db_status) -> TestSet:
    test_set = TestSet(
        name="in-flight-quota-test-set",
        user_id=db_user.id,
        organization_id=test_organization.id,
        status_id=db_status.id,
    )
    test_db.add(test_set)
    test_db.flush()
    for _ in range(3):
        test = Test(
            user_id=db_user.id, organization_id=test_organization.id, status_id=db_status.id
        )
        test_db.add(test)
        test_db.flush()
        test_db.execute(
            test_test_set_association.insert().values(
                test_id=test.id,
                test_set_id=test_set.id,
                organization_id=test_organization.id,
                user_id=db_user.id,
            )
        )
    test_db.commit()
    return test_set


def _add_run(test_db, org_id, user_id, config, status_name, total_tests, created_at=None):
    status = get_or_create_status(test_db, status_name, "TestRun", organization_id=str(org_id))
    run = TestRun(
        test_configuration_id=config.id,
        status_id=status.id,
        organization_id=org_id,
        user_id=user_id,
        attributes={"total_tests": total_tests},
    )
    if created_at is not None:
        run.created_at = created_at
    test_db.add(run)
    test_db.commit()
    return run


def test_a_queued_run_holds_back_its_tests(
    test_db, test_org_id, db_user, db_test_configuration, three_test_set
):
    """5 used + 4 queued leaves 1, so a 3-test run is refused."""
    increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 5)
    _add_run(test_db, test_org_id, db_user.id, db_test_configuration, "Queued", 4)

    with pytest.raises(QuotaExceededError) as exc_info:
        enforce_test_run_quota(test_db, test_org_id, str(db_user.id), three_test_set.id)

    assert exc_info.value.verdict.requested == 3
    assert exc_info.value.verdict.remaining == 1


def test_a_running_run_holds_back_its_tests(
    test_db, test_org_id, db_user, db_test_configuration, three_test_set
):
    increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 5)
    _add_run(test_db, test_org_id, db_user.id, db_test_configuration, "Progress", 4)

    with pytest.raises(QuotaExceededError):
        enforce_test_run_quota(test_db, test_org_id, str(db_user.id), three_test_set.id)


def test_finished_runs_hold_back_nothing(
    test_db, test_org_id, db_user, db_test_configuration, three_test_set
):
    """A finished run's tests are already in ``usage``; counting them again
    would charge twice."""
    increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 5)
    _add_run(test_db, test_org_id, db_user.id, db_test_configuration, "Completed", 4)

    enforce_test_run_quota(test_db, test_org_id, str(db_user.id), three_test_set.id)


def test_a_run_stuck_past_the_window_holds_back_nothing(
    test_db, test_org_id, db_user, db_test_configuration, three_test_set
):
    """A crashed worker can leave a run in "Progress" forever; it must not
    block the org for the rest of the period."""
    increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 5)
    stale = datetime.now(timezone.utc) - IN_FLIGHT_RUN_WINDOW - timedelta(hours=1)
    _add_run(test_db, test_org_id, db_user.id, db_test_configuration, "Progress", 4, stale)

    enforce_test_run_quota(test_db, test_org_id, str(db_user.id), three_test_set.id)
