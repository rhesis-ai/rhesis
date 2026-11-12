"""The job retention sweep reaches rows that belong to a project.

With an org bound and no project, the ORM filter and ``project_isolation`` both hide
project rows, so an org-only pass left them in place forever.
"""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

from rhesis.backend.app.models.activity_log import ActivityLog
from rhesis.backend.app.models.job import Job
from rhesis.backend.app.models.project import Project
from rhesis.backend.jobs import retention
from tests.backend.fixtures.rls import scope_session_to_org, scope_session_to_project
from tests.backend.jobs import test_retention as helpers

pytestmark = [pytest.mark.security, pytest.mark.integration]


def _project_rows(db, org, user, *, deleted=False):
    scope_session_to_org(db, org.id)
    project = Project(name=f"Retention {uuid.uuid4().hex[:6]}", organization_id=org.id)
    project.user_id = user.id
    db.add(project)
    db.commit()
    project_id = project.id
    scope_session_to_project(db, project_id)
    job = Job(
        organization_id=org.id,
        user_id=user.id,
        project_id=project_id,
        job_type="test.job",
        status="completed",
        finished_at=helpers._OLD,
    )
    db.add(job)
    db.flush()
    entry = ActivityLog(organization_id=org.id, project_id=project_id, level="info", message="x")
    entry.created_at = helpers._OLD
    db.add(entry)
    if deleted:
        project.deleted_at = helpers._OLD
    db.commit()
    ids = (str(project_id), str(job.id), str(entry.id))
    db.expunge_all()
    return ids


def _exists(db, org, project_id, table, row_id):
    scope_session_to_org(db, org.id)
    scope_session_to_project(db, project_id)
    db.expire_all()
    row = db.execute(text(f"SELECT 1 FROM {table} WHERE id = :id"), {"id": row_id}).first()
    scope_session_to_project(db, None)
    return row is not None


@pytest.mark.parametrize("deleted_project", [False, True], ids=["live", "deleted-project"])
def test_sweep_deletes_project_rows(real_commit_test_db, deleted_project):
    db = real_commit_test_db
    suffix = uuid.uuid4().hex[:6]
    org, user = helpers._org(
        db, f"Retention Project {suffix}", f"ret-proj-{suffix}@events-test.com"
    )
    project_id, job_id, entry_id = _project_rows(db, org, user, deleted=deleted_project)

    jobs, logs = retention._sweep_organization(str(org.id), helpers._NOW - timedelta(days=30))

    assert (jobs, logs) == (1, 1)
    assert not _exists(db, org, project_id, "job", job_id)
    assert not _exists(db, org, project_id, "activity_log", entry_id)
