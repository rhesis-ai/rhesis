import uuid
from typing import Any, Dict

from celery.result import AsyncResult
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app import schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_db_session
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.celery.core import app as celery_app
from rhesis.backend.jobs.utils import get_test_run_by_task_id

router = RhesisRouter(
    prefix="/jobs",
    tags=["jobs"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
    resource="job",
)


def _task_status_payload(celery_task_id: str) -> Dict[str, Any]:
    """Read a Celery task's status from the result backend.

    ``AsyncResult`` has no ``.error`` attribute -- on failure the exception
    itself is what ``.result`` holds, which is also why "result" must be
    suppressed on failure rather than shown alongside "error".
    """
    result = AsyncResult(celery_task_id, app=celery_app)
    failed = result.failed()
    return {
        "task_id": celery_task_id,
        "status": result.status,
        "result": result.result if result.ready() and not failed else None,
        "error": str(result.result) if failed else None,
    }


@router.get("/by-celery-id/{celery_task_id}")
async def get_task_status_by_celery_id(
    celery_task_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Get the status of a background task (e.g. test execution) by Celery task ID.

    STOPGAP ownership check: there is no ``job`` table yet, so the only way to
    prove a Celery task id belongs to the caller's organization is to find a
    ``TestRun`` row that recorded it. ``organization_id`` is passed explicitly
    rather than left to the session's ambient scope: the query builder treats
    a missing ``organization_id`` as an error for any model that has the
    column (see ``QueryBuilder.with_organization_filter``), so passing it
    explicitly is what makes this a real ownership check rather than an
    always-empty one.

    This only covers test-execution tasks. Other task types (test set
    generation, Garak import, ...) have no queryable owner yet, so the lookup
    misses and the request is denied rather than served unverified: failing
    closed is the safe default while this stopgap is in place. Replaced by an
    indexed lookup against ``job.celery_task_id`` once the jobs table lands,
    which will cover every job type uniformly.
    """
    test_run = get_test_run_by_task_id(
        db, str(celery_task_id), organization_id=str(current_user.organization_id)
    )
    if test_run is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return _task_status_payload(str(celery_task_id))


@router.get("/{task_id}", deprecated=True)
async def get_task_status(
    task_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Deprecated alias for ``GET /jobs/by-celery-id/{celery_task_id}``.

    Kept so the routers that already document this path as their polling
    target keep working. Will be removed once ``GET /jobs/{id}`` is reclaimed
    for job UUIDs.
    """
    return await get_task_status_by_celery_id(task_id, db=db, current_user=current_user)
