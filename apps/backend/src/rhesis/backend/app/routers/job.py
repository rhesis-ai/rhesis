import uuid
from typing import Any, Dict

from celery.result import AsyncResult
from fastapi import Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.crud import job as job_crud
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.celery.core import app as celery_app

router = RhesisRouter(
    prefix="/jobs",
    tags=["jobs"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
    resource="job",
)


def _celery_status(celery_task_id: str) -> Dict[str, Any]:
    """Read a Celery task's live state from the result backend.

    ``AsyncResult`` has no ``.error`` attribute -- on failure the exception
    itself is what ``.result`` holds, which is also why "result" is suppressed
    on failure rather than shown alongside "error".
    """
    result = AsyncResult(celery_task_id, app=celery_app)
    failed = result.failed()
    return {
        "task_id": celery_task_id,
        "status": result.status,
        "result": result.result if result.ready() and not failed else None,
        "error": str(result.result) if failed else None,
    }


def _resolve_job(db: Session, job_id: uuid.UUID, organization_id: str, user_id: str) -> models.Job:
    job = job_crud.get_job(db, job_id, organization_id=organization_id, user_id=user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/", response_model=list[schemas.Job])
@with_count_header(model=models.Job)
def read_jobs(
    response: Response,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """List background jobs, newest first."""
    organization_id, user_id = tenant_context
    return job_crud.get_jobs(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/by-celery-id/{celery_task_id}")
def get_job_by_celery_id(
    celery_task_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get a job's live Celery status by the task id it was dispatched under.

    The ownership check is a single indexed read against ``job.celery_task_id``,
    so it covers every job type. It replaces a stopgap that could only verify
    test-execution tasks, because a ``TestRun`` row was the only place a task id
    was recorded before the ``job`` table existed.
    """
    organization_id, _ = tenant_context
    job = job_crud.get_job_by_celery_task_id(
        db, str(celery_task_id), organization_id=organization_id
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return _celery_status(str(celery_task_id))


@router.get("/{task_id}", deprecated=True)
def get_task_status(
    task_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Deprecated alias for ``GET /jobs/by-celery-id/{celery_task_id}``.

    Several routers document this path as their polling target. Kept working so
    they keep working, and so ``GET /jobs/{id}`` can later be reclaimed for a
    job UUID.
    """
    return get_job_by_celery_id(
        task_id, db=db, tenant_context=tenant_context, current_user=current_user
    )


@router.get("/detail/{job_id}", response_model=schemas.Job)
def read_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get one job by its own id.

    Under ``/detail/`` rather than ``/{job_id}`` because the deprecated alias
    above still owns the bare path. Both move once that alias is dropped.
    """
    organization_id, user_id = tenant_context
    return _resolve_job(db, job_id, organization_id, user_id)


@router.get("/detail/{job_id}/activity", response_model=schemas.JobActivity)
def read_job_activity(
    job_id: uuid.UUID,
    after_sequence: int | None = Query(
        None, description="Return only entries after this sequence number"
    ),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get a job's log entries, oldest first, from an optional cursor."""
    organization_id, user_id = tenant_context
    _resolve_job(db, job_id, organization_id, user_id)

    entries = job_crud.get_job_activity(db, job_id, after_sequence=after_sequence, limit=limit)
    next_after = entries[-1].sequence if entries else after_sequence
    return schemas.JobActivity(entries=entries, next_after_sequence=next_after)


@router.post(
    "/detail/{job_id}/cancel",
    response_model=schemas.Job,
    **capability(Permission.Job.CANCEL),
)
def cancel_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Ask a job to stop.

    Two steps, and neither alone is enough. ``revoke`` stops a job that has not
    started; it cannot stop a running one, because the workers use a thread pool
    where ``terminate=True`` would signal the whole process rather than the
    thread. So the row also moves to ``cancelling``, which is the request a
    running job checks for and acts on at its next checkpoint.

    That means the response says "cancelling", not "cancelled". Claiming the
    work had stopped would be a lie until the job acknowledges.
    """
    organization_id, user_id = tenant_context
    job = _resolve_job(db, job_id, organization_id, user_id)

    if not schemas.Job.model_validate(job).cancellable:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel a job with status '{job.status}'",
        )

    if job.celery_task_id:
        celery_app.control.revoke(job.celery_task_id)

    job_crud.request_cancel(db, job)
    db.commit()
    db.refresh(job)
    return job
