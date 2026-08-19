"""Recording what background work the platform is doing.

One ``job`` row per dispatch, created by :func:`~rhesis.backend.jobs.launch_job`
before the Celery message is published and advanced by ``BaseJob``'s lifecycle
hooks in the worker.

Every function here is best-effort and swallows its own failures. Bookkeeping
must never break the work it describes: a missing row costs visibility, an
exception raised out of here would cost the user their test run. The cost of
that choice is that a job with no row cannot be polled by id, which is a
visibility gap and not a data-integrity one.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.enums import JobStatus

logger = logging.getLogger(__name__)

# Job types that produce a row per request or per trace rather than per
# user-visible operation. A row each would bury the Jobs screen in noise that
# nobody asked to see, so they opt out.
UNTRACKED_JOB_TYPES = frozenset(
    {
        "usage.accrue_usage",
        "embedding.generate_embedding",
        "telemetry.enrich.enrich_trace_async",
        "telemetry.evaluate.evaluate_turn_trace_metrics",
        "telemetry.evaluate.evaluate_conversation_trace_metrics",
        "telemetry.post_ingest.post_ingest_link",
    }
)

_NAME_PREFIX = "rhesis.backend.jobs."


def job_type_for(task_name: str) -> str:
    """Strip our package prefix off a Celery task name.

    ``rhesis.backend.jobs.embedding.generate_embedding`` becomes
    ``embedding.generate_embedding`` -- short enough to show in a filter
    dropdown, still unambiguous.
    """
    if task_name.startswith(_NAME_PREFIX):
        return task_name[len(_NAME_PREFIX) :]
    return task_name


def is_tracked(task_name: str) -> bool:
    return job_type_for(task_name) not in UNTRACKED_JOB_TYPES


def create_job(
    db: Session,
    *,
    celery_task_id: str,
    task_name: str,
    name: Optional[str] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    job_metadata: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Optional[UUID]:
    """Record a queued job on the caller's session. Returns its id, or None.

    Added and flushed but deliberately **not committed**: the row belongs to
    whatever transaction the caller is already in, and committing here would
    also commit their unrelated pending work. Flushing is enough to make the id
    available and to surface a constraint problem while it can still be logged.
    """
    from rhesis.backend.app.models.job import Job

    if not is_tracked(task_name):
        return None

    try:
        job = Job(
            celery_task_id=celery_task_id,
            job_type=job_type_for(task_name),
            name=name,
            status=JobStatus.QUEUED.value,
            queued_at=datetime.now(timezone.utc),
            entity_type=entity_type,
            entity_id=entity_id,
            job_metadata=job_metadata,
            trace_id=trace_id,
        )
        # Set explicitly rather than relying on auto_stamp: launch_job has
        # already resolved these, and a script-dispatched job may have no
        # ambient scope to stamp from.
        if organization_id:
            job.organization_id = organization_id
        if user_id:
            job.user_id = user_id
        if project_id:
            job.project_id = project_id

        db.add(job)
        db.flush()
        return job.id
    except Exception as exc:
        logger.warning(
            f"Could not record job row for {task_name} ({celery_task_id}): {exc}",
            exc_info=True,
        )
        return None


def _update_by_celery_id(
    celery_task_id: str,
    organization_id: str,
    user_id: str,
    project_id: str,
    changes: Dict[str, Any],
) -> None:
    """Apply changes to the job with this Celery id, on its own session.

    Its own session because the caller is a Celery lifecycle hook: there is no
    ambient request transaction to join, and a status update must land even if
    the task body's own transaction is about to roll back -- a job that failed
    is exactly when its row matters most.
    """
    from rhesis.backend.app.database import get_db_with_tenant_variables
    from rhesis.backend.app.models.job import Job

    try:
        with get_db_with_tenant_variables(
            organization_id or "", user_id or "", project_id or ""
        ) as db:
            job = db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
            if job is None:
                # Normal for untracked job types and for anything dispatched
                # before this feature shipped.
                return
            for field, value in changes.items():
                setattr(job, field, value)
            db.commit()
    except Exception as exc:
        logger.warning(
            f"Could not update job row for {celery_task_id}: {exc}",
            exc_info=True,
        )


def mark_running(celery_task_id: str, organization_id: str, user_id: str, project_id: str) -> None:
    _update_by_celery_id(
        celery_task_id,
        organization_id,
        user_id,
        project_id,
        {"status": JobStatus.RUNNING.value, "started_at": datetime.now(timezone.utc)},
    )


def mark_completed(
    celery_task_id: str, organization_id: str, user_id: str, project_id: str
) -> None:
    _update_by_celery_id(
        celery_task_id,
        organization_id,
        user_id,
        project_id,
        {"status": JobStatus.COMPLETED.value, "finished_at": datetime.now(timezone.utc)},
    )


def mark_failed(
    celery_task_id: str,
    organization_id: str,
    user_id: str,
    project_id: str,
    *,
    error: BaseException,
) -> None:
    _update_by_celery_id(
        celery_task_id,
        organization_id,
        user_id,
        project_id,
        {
            "status": JobStatus.FAILED.value,
            "finished_at": datetime.now(timezone.utc),
            "error_message": str(error),
            "error_type": type(error).__name__,
        },
    )


def mark_retrying(
    celery_task_id: str, organization_id: str, user_id: str, project_id: str, *, attempt: int
) -> None:
    """Record a retry without moving the job out of ``running``.

    A retry is not a terminal state, so status stays put; only the attempt
    counter moves, so a job that succeeded on its third try does not look like
    one that succeeded first time.
    """
    _update_by_celery_id(
        celery_task_id,
        organization_id,
        user_id,
        project_id,
        {"attempt": attempt},
    )


def mark_cancelled(
    celery_task_id: str, organization_id: str, user_id: str, project_id: str
) -> None:
    _update_by_celery_id(
        celery_task_id,
        organization_id,
        user_id,
        project_id,
        {"status": JobStatus.CANCELLED.value, "finished_at": datetime.now(timezone.utc)},
    )


def set_progress(
    celery_task_id: str,
    organization_id: str,
    user_id: str,
    project_id: str,
    *,
    current: int,
    total: Optional[int] = None,
) -> None:
    changes: Dict[str, Any] = {"progress_current": current}
    if total is not None:
        changes["progress_total"] = total
    _update_by_celery_id(celery_task_id, organization_id, user_id, project_id, changes)
