"""launch_job emits JobQueued through the real dispatch path, so a tracked
job gets its first activity_log entry before the Celery message is even
published -- and its Job.trace_id is populated (see events/correlation.py).

Separate from test_job_lifecycle_activity_log.py, which exercises the
in-worker hooks (BaseJob._advance_job_row, task_revoked); this is the router
side.
"""

from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from rhesis.backend.app.models.activity_log import ActivityLog
from rhesis.backend.app.models.job import Job
from rhesis.backend.jobs import launch_job
from tests.backend.fixtures.test_setup import create_test_organization_and_user


class TestLaunchJobQueuedEvent:
    def test_writes_a_job_queued_activity_log_row(self, real_commit_test_db: Session):
        db = real_commit_test_db
        org, user, _ = create_test_organization_and_user(
            db, "Events Smoke Org", "eventssmoke@launch-test.com", "Events Smoke User"
        )
        user.organization_id = org.id
        # ActivityLogSink opens its own DB connection, so the org row must be
        # genuinely committed, not just flushed on this session, or that
        # connection cannot see it yet.
        db.commit()

        task = MagicMock()
        task.name = "rhesis.backend.jobs.generate_and_save_test_set"
        task.display_name = "Generate Test Set"
        task.apply_async.return_value = MagicMock(id="unused")

        launch_job(task, current_user=user, db=db)

        dispatched_id = task.apply_async.call_args.kwargs["task_id"]
        db.expire_all()
        job = db.query(Job).filter(Job.celery_task_id == dispatched_id).first()
        assert job is not None
        assert job.trace_id is not None and len(job.trace_id) == 32

        entry = db.query(ActivityLog).filter(ActivityLog.job_id == job.id).first()
        assert entry is not None, "launch_job must produce a JobQueued activity_log row"
        assert entry.message == "Job queued"
        assert entry.level == "info"
        assert entry.sequence == 1

    def test_untracked_job_type_gets_no_activity_log_row(self, real_commit_test_db: Session):
        """UNTRACKED_JOB_TYPES exists to keep high-frequency internal tasks
        off the Jobs screen; JobQueued must respect the same opt-out or it
        recreates the exact noise that list was built to avoid."""
        db = real_commit_test_db
        org, user, _ = create_test_organization_and_user(
            db, "Events Untracked Org", "eventsuntracked@launch-test.com", "User"
        )
        user.organization_id = org.id
        db.commit()

        before = db.query(ActivityLog).count()

        task = MagicMock()
        task.name = "rhesis.backend.jobs.usage.accrue_usage"
        task.apply_async.return_value = MagicMock(id="unused")

        launch_job(task, current_user=user, db=db)

        assert db.query(ActivityLog).count() == before
