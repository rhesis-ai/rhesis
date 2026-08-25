"""A job's real lifecycle hooks produce a real, ordered activity_log
narrative -- the actual deliverable: the Jobs screen's detail view stops
being empty.

Goes through ``BaseJob._advance_job_row`` and ``launch_job`` themselves, not
the tracking helpers directly, so a wiring mistake that leaves the emit call
unreached still fails here (same principle as test_launch_job_records.py).
"""

import uuid

from sqlalchemy.orm import Session

from rhesis.backend.app.models.activity_log import ActivityLog
from rhesis.backend.app.models.job import Job
from tests.backend.fixtures.test_setup import create_test_organization_and_user


def _job_row(db: Session, org, user) -> str:
    from rhesis.backend.jobs import tracking

    celery_task_id = str(uuid.uuid4())
    tracking.create_job(
        db,
        celery_task_id=celery_task_id,
        task_name="rhesis.backend.jobs.generate_and_save_test_set",
        organization_id=str(org.id),
        user_id=str(user.id),
    )
    db.commit()
    return celery_task_id


def _task(celery_task_id: str, org, user):
    """Borrow a real registered task; see test_launch_job_records.py for why
    not ``BaseJob()`` directly. Callers must pop the request.
    """
    from rhesis.backend.celery.core import app as celery_app

    task = celery_app.tasks["rhesis.backend.jobs.generate_and_save_test_set"]
    task.push_request(
        id=celery_task_id,
        organization_id=str(org.id),
        user_id=str(user.id),
        project_id=None,
    )
    return task


class TestJobLifecycleActivityLog:
    def test_running_then_completed_writes_two_ordered_entries(self, real_commit_test_db: Session):
        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Activity Org", "activity@launch-test.com", "Activity User"
        )
        celery_task_id = _job_row(real_commit_test_db, org, user)
        task = _task(celery_task_id, org, user)

        try:
            task._advance_job_row("running")
            task._advance_job_row("completed")
        finally:
            task.pop_request()

        real_commit_test_db.expire_all()
        job = real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
        entries = (
            real_commit_test_db.query(ActivityLog)
            .filter(ActivityLog.job_id == job.id)
            .order_by(ActivityLog.sequence)
            .all()
        )

        assert [e.message for e in entries] == ["Job started", "Job completed successfully"]
        assert [e.sequence for e in entries] == [1, 2]
        assert all(e.level == "info" for e in entries)
        # Every entry ties back to the job's own trace_id -- the same
        # correlation id a support engineer would follow from the row to
        # its narrative.
        assert all(e.job_id == job.id for e in entries)

    def test_failed_writes_an_error_level_entry_with_the_exception_text(
        self, real_commit_test_db: Session
    ):
        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Activity Org Fail", "activityfail@launch-test.com", "User"
        )
        celery_task_id = _job_row(real_commit_test_db, org, user)
        task = _task(celery_task_id, org, user)

        try:
            task._advance_job_row("failed", error=RuntimeError("endpoint unreachable"))
        finally:
            task.pop_request()

        real_commit_test_db.expire_all()
        job = real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
        entry = real_commit_test_db.query(ActivityLog).filter(ActivityLog.job_id == job.id).first()

        assert entry.level == "error"
        assert entry.message == "Job failed: RuntimeError: endpoint unreachable"

    def test_a_narrative_failure_does_not_block_the_status_transition(
        self, real_commit_test_db: Session
    ):
        """The two layers (job status, activity narrative) fail independently
        -- a broken log write must never leave the job row stuck."""
        from unittest.mock import patch

        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Activity Org Iso", "activityiso@launch-test.com", "User"
        )
        celery_task_id = _job_row(real_commit_test_db, org, user)
        task = _task(celery_task_id, org, user)

        try:
            with patch("rhesis.backend.events.emit", side_effect=RuntimeError("sink exploded")):
                task._advance_job_row("running")  # must not raise
        finally:
            task.pop_request()

        real_commit_test_db.expire_all()
        job = real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
        assert job.status == "running", "the job row must still advance"

    def test_cooperative_cancellation_writes_a_cancelled_entry(self, real_commit_test_db: Session):
        """The retval={"status": "cancelled"} path on_success uses to tell a
        cooperative stop from a real success (see base.py's
        _job_transition_for_success)."""
        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Activity Org Cancel", "activitycancel@launch-test.com", "User"
        )
        celery_task_id = _job_row(real_commit_test_db, org, user)
        task = _task(celery_task_id, org, user)

        try:
            task.on_success({"status": "cancelled"}, celery_task_id, [], {})
        finally:
            task.pop_request()

        real_commit_test_db.expire_all()
        job = real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
        entry = real_commit_test_db.query(ActivityLog).filter(ActivityLog.job_id == job.id).first()

        assert job.status == "cancelled"
        assert entry.message == "Job cancelled"


class TestTaskRevokedCancelsActivityLog:
    """The other cancellation path: a task revoked before it ever started, so
    _advance_job_row never runs for it at all."""

    def test_revoked_before_start_writes_a_cancelled_entry(self, real_commit_test_db: Session):
        from rhesis.backend.celery.signals import _mark_job_cancelled

        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Activity Org Revoke", "activityrevoke@launch-test.com", "User"
        )
        celery_task_id = _job_row(real_commit_test_db, org, user)

        _mark_job_cancelled(
            celery_task_id,
            "rhesis.backend.jobs.generate_and_save_test_set",
            {"organization_id": str(org.id), "user_id": str(user.id)},
        )

        real_commit_test_db.expire_all()
        job = real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
        entry = real_commit_test_db.query(ActivityLog).filter(ActivityLog.job_id == job.id).first()

        assert job.status == "cancelled"
        assert entry is not None, "a task revoked before it started must still get a log entry"
        assert entry.message == "Job cancelled"
