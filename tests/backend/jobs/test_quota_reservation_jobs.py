"""A job launched with a reservation settles it once, on whichever path ends it.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/jobs/test_quota_reservation_jobs.py -v
"""

import uuid
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, Mock, patch

import pytest

from rhesis.backend.app.models.job import Job
from rhesis.backend.app.quota import OveragePolicy, QuotaPolicy, QuotaRegistry, QuotaResource
from rhesis.backend.app.quota.enforcement import (
    QuotaExceededError,
    QuotaReservation,
    _read_usage,
    reserve_quota,
)
from rhesis.backend.celery.signals import handle_task_revoked
from rhesis.backend.jobs import launch_reserved_job
from rhesis.backend.jobs.base import BaseJob
from rhesis.backend.jobs.quota import Settled, settle_job_reservation

RESOURCE = QuotaResource.TEST_GENERATION
WIRE = {
    "org_id": "org-1",
    "resource": RESOURCE.value,
    "amount": 10,
    "period_start": "2026-11-01",
}
SETTLE = "rhesis.backend.jobs.quota.settle_job_reservation"


class _Task(BaseJob):
    """Celery's ``request`` is a read-only property, so override it here."""

    def __init__(self):
        self._request = Mock(spec=["id", "headers", "retries"])
        self._request.id = "task-1"
        self._request.headers = {}
        self.get_tenant_context = Mock(return_value=("org-1", "user-1", "proj-1"))
        self.log_with_context = Mock()
        self.db = MagicMock()

    @property
    def request(self):
        return self._request

    @contextmanager
    def get_db_session(self):
        yield self.db


class TestWireForm:
    def test_round_trip(self):
        reservation = QuotaReservation("org-1", RESOURCE, 10, date(2026, 11, 1))
        assert reservation.to_wire() == WIRE
        assert QuotaReservation.from_wire(WIRE) == reservation

    def test_unlimited_reservation_has_no_period(self):
        reservation = QuotaReservation("org-1", RESOURCE, 10, None)
        assert QuotaReservation.from_wire(reservation.to_wire()).period_start is None


class TestSettleQuota:
    def test_settles_through_the_job_row(self):
        task = _Task()
        with patch(SETTLE, return_value=Settled.NOW) as settle:
            task.settle_quota(RESOURCE, 4, WIRE)

        settle.assert_called_once_with("task-1", ("org-1", "user-1", "proj-1"), 4)

    def test_without_a_job_row_settles_once_per_run(self):
        task = _Task()
        with (
            patch(SETTLE, return_value=Settled.NO_ROW),
            patch.object(QuotaReservation, "settle") as settle,
        ):
            task.settle_quota(RESOURCE, 4, WIRE)
            task.settle_quota(RESOURCE, 4, WIRE)

        settle.assert_called_once_with(task.db, 4)

    def test_accrues_without_a_reservation(self):
        task = _Task()
        with patch("rhesis.backend.app.services.usage.dispatch_accrual") as accrue:
            task.settle_quota(RESOURCE, 4, None)

        accrue.assert_called_once_with("org-1", RESOURCE, 4)


class TestReleaseOnFailure:
    def test_permanent_failure_releases_the_reservation(self):
        task = _Task()
        task._advance_job_row = Mock()
        task._fail_linked_test_run = Mock()
        task._get_execution_time = Mock(return_value="1s")
        task.send_email_notification_flag = False
        task._request.retries = task.max_retries
        with (
            patch(SETTLE, return_value=Settled.NOW) as settle,
            patch("celery.Task.on_failure", return_value=None),
        ):
            BaseJob.on_failure(
                task, RuntimeError("boom"), "task-1", (), {"quota_reservation": WIRE}, None
            )

        settle.assert_called_once_with("task-1", ("org-1", "user-1", "proj-1"), 0)


class TestLaunchReservedJob:
    def test_reserves_then_launches_with_the_reservation(self):
        org, db = Mock(id="org-1"), Mock()
        reservation = QuotaReservation("org-1", RESOURCE, 7, date(2026, 11, 1))
        with (
            patch(
                "rhesis.backend.app.quota.enforcement.reserve_quota", return_value=reservation
            ) as reserve,
            patch("rhesis.backend.jobs.launch_job", return_value="result") as launch,
        ):
            result = launch_reserved_job("task", org=org, resource=RESOURCE, amount=7, db=db, x=1)

        assert result == "result"
        reserve.assert_called_once_with(db, "org-1", org, RESOURCE, 7)
        launch.assert_called_once_with("task", db=db, quota_reservation=reservation.to_wire(), x=1)

    def test_does_not_launch_when_the_amount_does_not_fit(self):
        with (
            patch(
                "rhesis.backend.app.quota.enforcement.reserve_quota",
                side_effect=QuotaExceededError(Mock()),
            ),
            patch("rhesis.backend.jobs.launch_job") as launch,
        ):
            with pytest.raises(QuotaExceededError):
                launch_reserved_job(
                    "task", org=Mock(id="org-1"), resource=RESOURCE, amount=7, db=Mock()
                )

        launch.assert_not_called()

    def test_a_failed_launch_gives_the_reservation_back(self):
        db = Mock()
        reservation = Mock()
        with (
            patch("rhesis.backend.app.quota.enforcement.reserve_quota", return_value=reservation),
            patch("rhesis.backend.jobs.launch_job", side_effect=RuntimeError("broker down")),
        ):
            with pytest.raises(RuntimeError):
                launch_reserved_job(
                    "task", org=Mock(id="org-1"), resource=RESOURCE, amount=7, db=db
                )

        reservation.settle.assert_called_once_with(db, 0)


class _FixedPolicyProvider:
    def __init__(self, policy: QuotaPolicy):
        self._policy = policy

    def get_policy(self, org=None) -> QuotaPolicy:
        return self._policy


@pytest.fixture
def reserved_job(test_db, test_org_id, authenticated_user_id):
    """A job row holding a real 10-unit reservation, with job sessions on ``test_db``."""
    saved = QuotaRegistry._provider
    QuotaRegistry.reset()
    QuotaRegistry.set_quota_provider(
        _FixedPolicyProvider(QuotaPolicy(limits={RESOURCE: 100}, overage=OveragePolicy.HARD))
    )

    @contextmanager
    def _same_session(*_args, **_kwargs):
        yield test_db

    reservation = reserve_quota(test_db, test_org_id, None, RESOURCE, 10)
    task_id = str(uuid.uuid4())
    test_db.add(
        Job(
            celery_task_id=task_id,
            job_type="test_set_generation",
            status="queued",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            quota_reservation=reservation.to_wire(),
        )
    )
    test_db.commit()
    with patch("rhesis.backend.app.database.get_db_with_tenant_variables", _same_session):
        yield task_id, (test_org_id, authenticated_user_id, None)
    QuotaRegistry._provider = saved


def _used(test_db, org_id):
    return _read_usage(test_db, org_id, RESOURCE)


class TestSettleAgainstTheDatabase:
    def test_settles_once_and_gives_back_the_unused_part(self, reserved_job, test_db, test_org_id):
        task_id, tenant = reserved_job
        assert _used(test_db, test_org_id) == 10

        assert settle_job_reservation(task_id, tenant, 3) is Settled.NOW
        assert _used(test_db, test_org_id) == 3

        # A redelivery, a retry or a revoke after the fact changes nothing.
        assert settle_job_reservation(task_id, tenant, 0) is Settled.ALREADY
        assert _used(test_db, test_org_id) == 3

    def test_a_revoked_job_gives_its_reservation_back(self, reserved_job, test_db, test_org_id):
        task_id, (org_id, user_id, _) = reserved_job
        request = Mock(
            id=task_id,
            task="rhesis.backend.jobs.generate_and_save_test_set",
            kwargs={"quota_reservation": {"amount": 10}},
            headers={"organization_id": org_id, "user_id": user_id},
        )

        handle_task_revoked(request=request)

        assert _used(test_db, test_org_id) == 0
        assert settle_job_reservation(task_id, (org_id, user_id, None), 5) is Settled.ALREADY

    def test_a_task_without_a_job_row(self, reserved_job):
        _, tenant = reserved_job
        assert settle_job_reservation(str(uuid.uuid4()), tenant, 0) is Settled.NO_ROW
