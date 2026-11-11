"""Per-organization cap on heavy background jobs.

Workers are shared and take jobs in order, so one organization queueing many long jobs
would hold every worker thread. The cap counts the org's unfinished heavy jobs across
all of its projects (project RLS hides other projects' rows from a scoped session).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from rhesis.backend.app.config import settings
from rhesis.backend.app.models.enums import JobStatus
from rhesis.backend.app.models.job import Job
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.services.job_capacity import (
    QUEUED_JOB_WINDOW,
    JobCapacityExceededError,
    enforce_job_capacity,
    running_job_window,
)
from rhesis.backend.jobs import launch_job
from tests.backend.fixtures.rls import scope_to_project

LIMIT = 3


@pytest.fixture(autouse=True)
def job_cap(monkeypatch):
    monkeypatch.setenv("MAX_ACTIVE_JOBS_PER_ORG", str(LIMIT))
    settings.get_job_limit_settings.cache_clear()
    yield
    settings.get_job_limit_settings.cache_clear()


def _add_job(db, org_id, project_id=None, job_type="execute_test_configuration", **fields):
    scope_to_project(db, project_id)
    job = Job(
        celery_task_id=str(uuid.uuid4()),
        job_type=job_type,
        status=fields.pop("status", JobStatus.QUEUED.value),
        queued_at=fields.pop("queued_at", datetime.now(timezone.utc)),
        organization_id=org_id,
        project_id=project_id,
        **fields,
    )
    db.add(job)
    db.commit()
    scope_to_project(db, None)
    return job


@pytest.fixture
def other_project(test_db, test_organization, db_user, db_status):
    project = Project(
        name="job-cap-other-project",
        organization_id=test_organization.id,
        user_id=db_user.id,
        status_id=db_status.id,
    )
    test_db.add(project)
    test_db.flush()
    return project


def test_jobs_in_every_project_count_toward_the_cap(test_db, test_org_id, db_user, other_project):
    user_id = str(db_user.id)
    _add_job(test_db, test_org_id)
    _add_job(test_db, test_org_id, other_project.id)
    enforce_job_capacity(test_db, test_org_id, user_id)

    _add_job(test_db, test_org_id, other_project.id, job_type="generate_and_save_test_set")

    with pytest.raises(JobCapacityExceededError) as exc_info:
        enforce_job_capacity(test_db, test_org_id, user_id)
    assert exc_info.value.status_code == 429


def test_finished_light_and_stale_jobs_do_not_count(test_db, test_org_id, db_user):
    now = datetime.now(timezone.utc)
    for status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        _add_job(test_db, test_org_id, status=status.value)
    _add_job(test_db, test_org_id, job_type="count_test_sets")
    # Never reached a terminal status: a dead worker, a lost message.
    _add_job(
        test_db,
        test_org_id,
        status=JobStatus.RUNNING.value,
        queued_at=now - running_job_window() - timedelta(hours=1),
        started_at=now - running_job_window() - timedelta(minutes=1),
    )
    _add_job(test_db, test_org_id, queued_at=now - QUEUED_JOB_WINDOW - timedelta(minutes=1))

    enforce_job_capacity(test_db, test_org_id, str(db_user.id))


def test_long_waits_and_long_runs_still_count(test_db, test_org_id, db_user):
    now = datetime.now(timezone.utc)
    # Waited hours behind a backlog: the case the cap exists for.
    _add_job(test_db, test_org_id, queued_at=now - timedelta(hours=5))
    _add_job(test_db, test_org_id, queued_at=now - timedelta(hours=6))
    # Queued long ago, started recently: counts from when it started.
    _add_job(
        test_db,
        test_org_id,
        status=JobStatus.RUNNING.value,
        queued_at=now - timedelta(hours=10),
        started_at=now - running_job_window() + timedelta(minutes=5),
    )

    with pytest.raises(JobCapacityExceededError):
        enforce_job_capacity(test_db, test_org_id, str(db_user.id))


def test_running_window_follows_the_time_limits(monkeypatch):
    monkeypatch.setenv("EXECUTION_TIME_LIMIT", str(5 * 3600))
    settings.get_job_limit_settings.cache_clear()

    assert running_job_window() > timedelta(hours=5)


def test_zero_turns_the_cap_off(test_db, test_org_id, db_user, monkeypatch):
    for _ in range(LIMIT):
        _add_job(test_db, test_org_id)
    monkeypatch.setenv("MAX_ACTIVE_JOBS_PER_ORG", "0")
    settings.get_job_limit_settings.cache_clear()

    enforce_job_capacity(test_db, test_org_id, str(db_user.id))


def _fake_task(name):
    task = MagicMock()
    task.name = name
    del task.display_name
    task.apply_async.return_value = MagicMock(id="unused")
    return task


def test_launch_job_refuses_a_heavy_job_past_the_cap(test_db, test_org_id, db_user):
    db_user.organization_id = uuid.UUID(str(test_org_id))
    task = _fake_task("rhesis.backend.jobs.execute_test_configuration")
    for _ in range(LIMIT):
        launch_job(task, current_user=db_user, db=test_db)

    with pytest.raises(JobCapacityExceededError):
        launch_job(task, current_user=db_user, db=test_db)
    assert task.apply_async.call_count == LIMIT

    # Light jobs are not capped.
    light = _fake_task("rhesis.backend.jobs.count_test_sets")
    launch_job(light, current_user=db_user, db=test_db)
    light.apply_async.assert_called_once()


def test_route_refuses_with_429_before_doing_any_work(
    authenticated_client, test_db, test_org_id, db_user
):
    for _ in range(LIMIT):
        _add_job(test_db, test_org_id)

    response = authenticated_client.post(
        f"/test_sets/{uuid.uuid4()}/execute/{uuid.uuid4()}", json={}
    )

    assert response.status_code == 429, response.text
