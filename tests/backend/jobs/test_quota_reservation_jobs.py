"""A job launched with a reservation settles it, or gives it back when it fails for good.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/jobs/test_quota_reservation_jobs.py -v
"""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, Mock, patch

import pytest

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError, QuotaReservation
from rhesis.backend.jobs import launch_reserved_job
from rhesis.backend.jobs.base import BaseJob

RESOURCE = QuotaResource.TEST_GENERATION
WIRE = {
    "org_id": "org-1",
    "resource": RESOURCE.value,
    "amount": 10,
    "period_start": "2026-11-01",
}


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
    def test_settles_the_reservation_with_what_was_made(self):
        task = _Task()
        with patch.object(QuotaReservation, "settle") as settle:
            task.settle_quota(RESOURCE, 4, WIRE)

        settle.assert_called_once_with(task.db, 4)

    def test_accrues_without_a_reservation(self):
        task = _Task()
        with patch("rhesis.backend.app.services.usage.dispatch_accrual") as accrue:
            task.settle_quota(RESOURCE, 4, None)

        accrue.assert_called_once_with("org-1", RESOURCE, 4)


class TestReleaseOnFailure:
    def _fail(self, task, retries, kwargs):
        task._advance_job_row = Mock()
        task._fail_linked_test_run = Mock()
        task._get_execution_time = Mock(return_value="1s")
        task.send_email_notification_flag = False
        task._request.retries = retries
        with patch("celery.Task.on_failure", return_value=None):
            BaseJob.on_failure(task, RuntimeError("boom"), "task-1", (), kwargs, None)

    def test_permanent_failure_releases_the_reservation(self):
        task = _Task()
        with patch.object(QuotaReservation, "settle") as settle:
            self._fail(task, task.max_retries, {"quota_reservation": WIRE})

        settle.assert_called_once_with(task.db, 0)

    def test_a_retry_keeps_the_reservation(self):
        task = _Task()
        with patch.object(QuotaReservation, "settle") as settle:
            self._fail(task, 0, {"quota_reservation": WIRE})

        settle.assert_not_called()

    def test_a_settled_reservation_is_not_released_again(self):
        task = _Task()
        with patch.object(QuotaReservation, "settle") as settle:
            task.settle_quota(RESOURCE, 4, WIRE)
            self._fail(task, task.max_retries, {"quota_reservation": WIRE})

        settle.assert_called_once_with(task.db, 4)


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
