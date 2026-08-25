"""launch_job records a row, and BaseJob's hooks advance it.

Separate from test_job_tracking.py, which exercises the tracking helpers
directly. These tests go through the real dispatch and hook entry points, so a
helper that works but is never called still fails here.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/jobs/test_launch_job_records.py -v
"""

import uuid
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from rhesis.backend.app.models.enums import JobStatus
from rhesis.backend.app.models.job import Job
from rhesis.backend.jobs import launch_job
from tests.backend.fixtures.test_setup import create_test_organization_and_user


def _fake_task(name: str, display_name: str | None = None) -> MagicMock:
    task = MagicMock()
    task.name = name
    if display_name is not None:
        task.display_name = display_name
    else:
        del task.display_name
    task.apply_async.return_value = MagicMock(id="unused")
    return task


class TestLaunchJobRecording:
    def test_records_a_row_before_dispatch(self, test_db: Session):
        org, user, _ = create_test_organization_and_user(
            test_db, "Launch Org", "launch@launch-test.com", "Launch User"
        )
        user.organization_id = org.id
        task = _fake_task("rhesis.backend.jobs.generate_and_save_test_set", "Generate Test Set")

        launch_job(task, current_user=user, db=test_db)

        task.apply_async.assert_called_once()
        dispatched_id = task.apply_async.call_args.kwargs["task_id"]
        job = test_db.query(Job).filter(Job.celery_task_id == dispatched_id).first()
        assert job is not None, "dispatch happened but nothing was recorded"
        assert job.status == JobStatus.QUEUED.value
        assert job.name == "Generate Test Set"
        assert str(job.organization_id) == str(org.id)

    def test_honours_a_caller_supplied_celery_id(self, test_db: Session):
        """test_set.py pre-generates an id so it can stamp the row before dispatch."""
        org, user, _ = create_test_organization_and_user(
            test_db, "Launch Org Preset", "preset@launch-test.com", "Preset User"
        )
        user.organization_id = org.id
        preset = str(uuid.uuid4())
        task = _fake_task("rhesis.backend.jobs.generate_and_save_test_set")

        launch_job(task, current_user=user, db=test_db, celery_task_id=preset)

        assert task.apply_async.call_args.kwargs["task_id"] == preset
        assert test_db.query(Job).filter(Job.celery_task_id == preset).first() is not None

    def test_records_the_entity_link_when_given(self, test_db: Session):
        org, user, _ = create_test_organization_and_user(
            test_db, "Launch Org Entity", "entity@launch-test.com", "Entity User"
        )
        user.organization_id = org.id
        entity_id = str(uuid.uuid4())
        task = _fake_task("rhesis.backend.jobs.generate_and_save_test_set")

        launch_job(
            task,
            current_user=user,
            db=test_db,
            entity_type="TestSet",
            entity_id=entity_id,
        )

        job = test_db.query(Job).filter(Job.entity_id == entity_id).first()
        assert job.entity_type == "TestSet"

    def test_untracked_type_still_dispatches(self, test_db: Session):
        """Opting out of the Jobs screen must not opt out of running."""
        org, user, _ = create_test_organization_and_user(
            test_db, "Launch Org Untracked", "untracked@launch-test.com", "Untracked User"
        )
        user.organization_id = org.id
        before = test_db.query(Job).count()
        task = _fake_task("rhesis.backend.jobs.usage.accrue_usage")

        launch_job(task, current_user=user, db=test_db)

        task.apply_async.assert_called_once()
        assert test_db.query(Job).count() == before

    def test_recording_failure_does_not_block_dispatch(self, test_db: Session):
        """The whole point of best-effort: the work still runs."""
        org, user, _ = create_test_organization_and_user(
            test_db, "Launch Org Broken", "broken@launch-test.com", "Broken User"
        )
        user.organization_id = org.id
        task = _fake_task("rhesis.backend.jobs.generate_and_save_test_set")

        with patch(
            "rhesis.backend.jobs.tracking.create_job",
            side_effect=RuntimeError("bookkeeping exploded"),
        ):
            launch_job(task, current_user=user, db=test_db)

        task.apply_async.assert_called_once()


class TestBaseJobHooks:
    """The hooks resolve their own tenant context off self.request."""

    def _job_for(self, db: Session, org, user) -> str:
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

    def _base_job(self, celery_task_id: str, org, user):
        """Borrow a real registered task and give it a request context.

        Not ``BaseJob()`` directly: ``self.request`` is backed by a request
        stack that only exists on an app-bound task, so an unbound instance
        raises on both attribute assignment and ``push_request``. Taking the
        registered instance also means these assertions run against the same
        object production uses. Callers must pop the request.
        """
        from rhesis.backend.celery.core import app as celery_app

        job = celery_app.tasks["rhesis.backend.jobs.generate_and_save_test_set"]
        job.push_request(
            id=celery_task_id,
            organization_id=str(org.id),
            user_id=str(user.id),
            project_id=None,
        )
        return job

    def test_running_then_completed(self, real_commit_test_db: Session):
        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Hook Org", "hook@launch-test.com", "Hook User"
        )
        celery_task_id = self._job_for(real_commit_test_db, org, user)
        task = self._base_job(celery_task_id, org, user)
        try:
            task._advance_job_row("running")
            real_commit_test_db.expire_all()
            job = (
                real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
            )
            assert job.status == JobStatus.RUNNING.value
            assert job.started_at is not None

            task._advance_job_row("completed")
            real_commit_test_db.expire_all()
            real_commit_test_db.refresh(job)
            assert job.status == JobStatus.COMPLETED.value
        finally:
            task.pop_request()

    def test_missing_request_id_is_a_no_op(self, real_commit_test_db: Session):
        from rhesis.backend.celery.core import app as celery_app

        task = celery_app.tasks["rhesis.backend.jobs.generate_and_save_test_set"]
        task.push_request(id=None)
        try:
            task._advance_job_row("completed")
        finally:
            task.pop_request()

    def test_hook_never_raises(self, real_commit_test_db: Session):
        """A raising hook would turn bookkeeping into a task failure."""
        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Hook Org Raise", "hookraise@launch-test.com", "Hook User"
        )
        celery_task_id = self._job_for(real_commit_test_db, org, user)
        task = self._base_job(celery_task_id, org, user)
        try:
            with patch(
                "rhesis.backend.jobs.tracking.mark_completed",
                side_effect=RuntimeError("db gone"),
            ):
                task._advance_job_row("completed")
        finally:
            task.pop_request()

    def test_on_success_marks_completed_through_the_real_hook(self, real_commit_test_db: Session):
        """Exercises on_success itself, not just the _advance_job_row helper.

        SilentJob overrides on_success and used to skip _advance_job_row
        entirely -- a test that only calls the helper directly would not have
        caught that.
        """
        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Hook Org Success", "hooksuccess@launch-test.com", "Hook User"
        )
        celery_task_id = self._job_for(real_commit_test_db, org, user)
        task = self._base_job(celery_task_id, org, user)
        try:
            with patch.object(task, "log_with_context"):
                task.on_success({"total_tests": 3}, celery_task_id, [], {})
            real_commit_test_db.expire_all()
            job = (
                real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
            )
            assert job.status == JobStatus.COMPLETED.value
        finally:
            task.pop_request()

    def test_on_success_with_cancelled_retval_marks_cancelled(self, real_commit_test_db: Session):
        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Hook Org Cancel", "hookcancel@launch-test.com", "Hook User"
        )
        celery_task_id = self._job_for(real_commit_test_db, org, user)
        task = self._base_job(celery_task_id, org, user)
        try:
            with patch.object(task, "log_with_context"):
                task.on_success({"total_tests": 3, "status": "cancelled"}, celery_task_id, [], {})
            real_commit_test_db.expire_all()
            job = (
                real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
            )
            assert job.status == JobStatus.CANCELLED.value
        finally:
            task.pop_request()


class TestSilentJobOnSuccessAdvancesJobRow:
    """SilentJob overrides on_success but must still advance the job row.

    Regression test: SilentJob.on_success used to call
    ``super(BaseJob, self).on_success(...)``, which skips BaseJob.on_success
    (and therefore _advance_job_row) entirely. Every SilentJob-based task
    (test execution, embedding, architect chat, endpoint exploration) would
    stay "running" forever after a successful run.
    """

    def _job_for(self, db: Session, org, user) -> str:
        from rhesis.backend.jobs import tracking

        celery_task_id = str(uuid.uuid4())
        tracking.create_job(
            db,
            celery_task_id=celery_task_id,
            task_name="rhesis.backend.jobs.execute_test_configuration",
            organization_id=str(org.id),
            user_id=str(user.id),
        )
        db.commit()
        return celery_task_id

    def _silent_job(self, celery_task_id: str, org, user):
        from rhesis.backend.celery.core import app as celery_app

        job = celery_app.tasks["rhesis.backend.jobs.execute_test_configuration"]
        job.push_request(
            id=celery_task_id,
            organization_id=str(org.id),
            user_id=str(user.id),
            project_id=None,
        )
        return job

    def test_on_success_marks_completed(self, real_commit_test_db: Session):
        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Silent Org", "silent@launch-test.com", "Silent User"
        )
        celery_task_id = self._job_for(real_commit_test_db, org, user)
        task = self._silent_job(celery_task_id, org, user)
        try:
            with patch.object(task, "log_with_context"):
                task.on_success({"total_tests": 3}, celery_task_id, [], {})
            real_commit_test_db.expire_all()
            job = (
                real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
            )
            assert job.status == JobStatus.COMPLETED.value
        finally:
            task.pop_request()

    def test_on_success_with_cancelled_retval_marks_cancelled(self, real_commit_test_db: Session):
        org, user, _ = create_test_organization_and_user(
            real_commit_test_db, "Silent Org Cancel", "silentcancel@launch-test.com", "Silent User"
        )
        celery_task_id = self._job_for(real_commit_test_db, org, user)
        task = self._silent_job(celery_task_id, org, user)
        try:
            with patch.object(task, "log_with_context"):
                task.on_success({"total_tests": 3, "status": "cancelled"}, celery_task_id, [], {})
            real_commit_test_db.expire_all()
            job = (
                real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
            )
            assert job.status == JobStatus.CANCELLED.value
        finally:
            task.pop_request()
