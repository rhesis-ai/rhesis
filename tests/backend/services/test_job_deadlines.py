"""Failing job rows that outlived their time limit (app/services/job_deadlines.py)."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from rhesis.backend.app.models.enums import JobStatus
from rhesis.backend.app.models.job import Job
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.services.job_deadlines import (
    QUEUED_JOB_WINDOW,
    fail_overdue_jobs,
    running_job_window,
)
from rhesis.backend.jobs import job_deadlines as sweep_job
from tests.backend.fixtures.rls import scope_to_project

RUN = "execute_test_configuration"
NOW = datetime.now(timezone.utc)


def _add_job(db, org_id, project_id=None, job_type=RUN, status=JobStatus.RUNNING, **times):
    scope_to_project(db, project_id)
    job = Job(
        celery_task_id=str(uuid.uuid4()),
        job_type=job_type,
        status=status.value,
        organization_id=org_id,
        project_id=project_id,
        **times,
    )
    db.add(job)
    db.commit()
    job_id = job.id
    scope_to_project(db, None)
    return job_id


def _status(db, job_id, project_id=None):
    scope_to_project(db, project_id)
    db.expire_all()
    job = db.query(Job).filter(Job.id == job_id).one()
    scope_to_project(db, None)
    return job.status, job.error_type


@pytest.fixture
def other_project(test_db, test_organization, db_user, db_status):
    project = Project(
        name="job-deadline-other-project",
        organization_id=test_organization.id,
        user_id=db_user.id,
        status_id=db_status.id,
    )
    test_db.add(project)
    test_db.flush()
    return project


@pytest.mark.integration
class TestFailOverdueJobs:
    def test_fails_a_running_job_past_its_limit(self, test_db, test_org_id):
        overdue = NOW - running_job_window(RUN) - timedelta(minutes=1)
        recent = NOW - running_job_window(RUN) + timedelta(minutes=5)
        late = _add_job(test_db, test_org_id, queued_at=overdue, started_at=overdue)
        alive = _add_job(test_db, test_org_id, queued_at=overdue, started_at=recent)

        assert fail_overdue_jobs(test_db, test_org_id, now=NOW) == 1

        assert _status(test_db, late) == ("failed", "JobTimeLimitExceeded")
        assert _status(test_db, alive) == ("running", None)

    def test_each_type_has_its_own_limit(self, test_db, test_org_id, monkeypatch):
        from rhesis.backend.app.config import settings

        monkeypatch.setenv("METRIC_TUNING_TIME_LIMIT", "60")
        settings.get_job_limit_settings.cache_clear()
        try:
            # Past a tuning run's window, well inside a test run's.
            started = NOW - running_job_window("run_metric_tuning") - timedelta(minutes=1)
            tuning = _add_job(
                test_db, test_org_id, job_type="run_metric_tuning", started_at=started
            )
            run = _add_job(test_db, test_org_id, started_at=started)

            fail_overdue_jobs(test_db, test_org_id, now=NOW)
        finally:
            settings.get_job_limit_settings.cache_clear()

        assert _status(test_db, tuning)[0] == "failed"
        assert _status(test_db, run)[0] == "running"

    def test_fails_a_job_queued_for_too_long(self, test_db, test_org_id):
        lost = _add_job(
            test_db,
            test_org_id,
            job_type="count_test_sets",
            status=JobStatus.QUEUED,
            queued_at=NOW - QUEUED_JOB_WINDOW - timedelta(minutes=1),
        )
        waiting = _add_job(
            test_db, test_org_id, status=JobStatus.QUEUED, queued_at=NOW - timedelta(hours=5)
        )

        fail_overdue_jobs(test_db, test_org_id, now=NOW)

        assert _status(test_db, lost)[0] == "failed"
        assert _status(test_db, waiting)[0] == "queued"

    def test_reaches_every_project(self, test_db, test_org_id, other_project):
        long_ago = NOW - timedelta(days=2)
        in_project = _add_job(
            test_db, test_org_id, other_project.id, queued_at=long_ago, started_at=long_ago
        )

        assert fail_overdue_jobs(test_db, test_org_id, now=NOW) == 1

        assert _status(test_db, in_project, other_project.id)[0] == "failed"

    def test_leaves_finished_and_unlimited_jobs(self, test_db, test_org_id):
        long_ago = NOW - timedelta(days=2)
        done = _add_job(test_db, test_org_id, status=JobStatus.COMPLETED, started_at=long_ago)
        # No known limit, so no point at which it is surely dead.
        unlimited = _add_job(test_db, test_org_id, job_type="some.other_job", started_at=long_ago)

        assert fail_overdue_jobs(test_db, test_org_id, now=NOW) == 0

        assert _status(test_db, done)[0] == "completed"
        assert _status(test_db, unlimited)[0] == "running"


@pytest.mark.unit
def test_the_sweep_continues_past_an_organization_that_fails():
    def fail_for(organization_id):
        if organization_id == "a":
            raise RuntimeError("boom")
        return 2

    with (
        patch.object(sweep_job, "list_organization_ids", return_value=["a", "b"]),
        patch.object(sweep_job, "SessionLocal"),
        patch.object(sweep_job, "bind_scope_to_session"),
        patch.object(sweep_job, "fail_overdue_jobs", side_effect=lambda db, org: fail_for(org)),
    ):
        assert sweep_job.sweep_overdue_jobs.run() == {"failed": 2}
