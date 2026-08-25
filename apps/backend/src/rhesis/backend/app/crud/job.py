"""CRUD operations for background jobs and their activity log.

Reads only, plus the cancel-request write. Jobs are created by
``rhesis.backend.jobs.launch_job`` and advanced by ``BaseJob``'s lifecycle
hooks, not through here -- there is no create/update endpoint to back, and the
row is a record of what happened rather than something a user edits.

``get_job_by_celery_task_id`` is what replaced a lookup that loaded 100 test
runs and scanned a JSONB field in Python. It is a single indexed row read, and
unlike its predecessor it covers every job type rather than only test runs.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models
from rhesis.backend.app.models.enums import JobStatus
from rhesis.backend.app.utils.crud_utils import get_item_detail, get_items_detail
from rhesis.backend.app.utils.query_utils import include

logger = logging.getLogger(__name__)

_JOB_RELATED_FIELDS = (include(models.Job.user),)


def get_jobs(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: Optional[str] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[models.Job]:
    return get_items_detail(
        db,
        models.Job,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_JOB_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
    )


def get_job(
    db: Session,
    job_id,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[models.Job]:
    return get_item_detail(
        db,
        models.Job,
        job_id,
        related_fields=_JOB_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
    )


def get_job_by_celery_task_id(
    db: Session,
    celery_task_id: str,
    organization_id: Optional[str] = None,
) -> Optional[models.Job]:
    """Find a job by the Celery task id it was dispatched under.

    ``organization_id`` is passed through to the query rather than left to the
    session's ambient scope, so this is a real ownership check when it backs a
    status endpoint.
    """
    query = (
        db.query(models.Job)
        .options(joinedload(models.Job.user))
        .filter(models.Job.celery_task_id == celery_task_id)
    )
    if organization_id:
        query = query.filter(models.Job.organization_id == organization_id)
    return query.first()


def get_job_activity(
    db: Session,
    job_id,
    after_sequence: Optional[int] = None,
    limit: int = 200,
) -> List[models.ActivityLog]:
    """Return a job's log entries in order, optionally after a cursor.

    Ordered by ``sequence`` rather than ``created_at``: entries written in the
    same instant would otherwise come back in an arbitrary order, and the
    cursor needs a total order to page through without gaps or repeats.
    """
    query = (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.job_id == job_id)
        .order_by(models.ActivityLog.sequence.asc(), models.ActivityLog.created_at.asc())
    )
    if after_sequence is not None:
        query = query.filter(models.ActivityLog.sequence > after_sequence)
    return query.limit(limit).all()


def request_cancel(db: Session, job: models.Job) -> models.Job:
    """Move a job to ``cancelling`` and record the request.

    Not ``cancelled``: on a thread pool Celery cannot stop a running task, so
    the job is only actually stopped once it notices the request and exits.
    Recording the intermediate state is what lets the UI say "cancelling"
    honestly instead of claiming the work has stopped when it has not.
    """
    job.status = JobStatus.CANCELLING.value
    db.add(job)
    db.flush()
    return job
