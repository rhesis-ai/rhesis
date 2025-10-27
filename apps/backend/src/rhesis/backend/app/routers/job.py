import uuid
from typing import Any, Dict, List

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app import schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_db_session,
)
from rhesis.backend.tasks import task_launcher
from rhesis.backend.tasks.example_task import email_notification_test
from rhesis.backend.worker import app as celery_app

router = APIRouter(
    prefix="/jobs",
    tags=["tasks"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


# @router.get("/", response_model=TaskList)
async def list_tasks(
    current_user: schemas.User = Depends(require_current_user_or_token),
) -> Dict[str, List[str]]:
    """List all registered Celery tasks."""
    # Filter out internal Celery tasks (those starting with "celery.")
    user_tasks = [
        task_name for task_name in celery_app.tasks.keys() if not task_name.startswith("celery.")
    ]
    return {"tasks": sorted(user_tasks)}


# @router.get("/active", response_model=WorkerInfo)
async def list_active_tasks(current_user: schemas.User = Depends(require_current_user_or_token)):
    """List all currently running tasks."""
    inspector = celery_app.control.inspect()
    active = inspector.active()
    scheduled = inspector.scheduled()
    reserved = inspector.reserved()

    return {"active": active, "scheduled": scheduled, "reserved": reserved}


# @router.get("/stats", response_model=WorkerStats)
async def get_stats(current_user: schemas.User = Depends(require_current_user_or_token)):
    """Get statistics about the Celery workers and tasks."""
    inspector = celery_app.control.inspect()
    stats = inspector.stats()
    registered = inspector.registered()

    return {"stats": stats, "registered_tasks": registered, "total_tasks": len(celery_app.tasks)}


# @router.post("/email-notification-test", response_model=TaskResponse)
async def test_email_notifications(
    message: str = "Test email notification",
    db: Session = Depends(get_tenant_db_session),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """
    Test the email notification system by running a simple task that will send
    an email upon completion.

    This endpoint is useful for verifying that:
    1. SMTP configuration is working in the worker
    2. Email notifications are being sent on task completion
    3. The email template and content are correct
    """
    try:
        # Use task_launcher to handle context
        result = task_launcher(
            email_notification_test, test_message=message, current_user=current_user
        )

        return {
            "task_id": result.id,
            "message": (
                "Email notification test task submitted. "
                "You should receive an email when it completes."
            ),
            "user_email": current_user.email if hasattr(current_user, "email") else None,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to submit email notification test: {str(e)}"
        )


# @router.post("/{task_name}", response_model=TaskResponse)
async def create_task(
    task_name: str,
    payload: Dict[Any, Any],
    db: Session = Depends(get_tenant_db_session),
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """
    Submit a new task to Celery.

    Uses task_launcher to automatically add context from current user.
    """
    try:
        # Get the task by name
        task_path = f"rhesis.backend.tasks.{task_name}"
        if task_path not in celery_app.tasks:
            raise HTTPException(status_code=404, detail=f"Task {task_name} not found")

        task = celery_app.tasks[task_path]

        # Use task_launcher to handle context
        result = task_launcher(task, current_user=current_user, **payload)

        return {"task_id": result.id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task {task_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# @router.get("/{task_id}", response_model=TaskStatus)
async def get_task_status(
    task_id: uuid.UUID, current_user: schemas.User = Depends(require_current_user_or_token)
):
    """Get the status of a task."""
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
        "error": str(result.error) if result.failed() else None,
    }


# @router.delete("/{task_id}", response_model=TaskRevoke)
async def revoke_task(
    task_id: uuid.UUID,
    terminate: bool = False,
    current_user: schemas.User = Depends(require_current_user_or_token),
):
    """Revoke a task (prevent it from being executed if not already running)."""
    celery_app.control.revoke(task_id, terminate=terminate)
    return {"message": f"Task {task_id} revoked"}


# @router.get("/health", response_model=HealthCheck)
async def health_check(current_user: schemas.User = Depends(require_current_user_or_token)):
    """Check if the Celery workers are running and responding."""
    try:
        inspector = celery_app.control.inspect()
        stats = inspector.stats()
        if not stats:
            raise HTTPException(status_code=503, detail="No Celery workers available")
        return {
            "status": "healthy",
            "workers": len(stats),
            "tasks_registered": len(celery_app.tasks),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Celery health check failed: {str(e)}")


# @router.get("/workers/status", response_model=WorkerStatus)
async def get_workers_status(current_user: schemas.User = Depends(require_current_user_or_token)):
    """Get detailed status of all Celery workers and their tasks."""
    inspector = celery_app.control.inspect()

    try:
        return {
            "active": inspector.active() or {},
            "reserved": inspector.reserved() or {},
            "registered_tasks": inspector.registered() or {},
            "stats": inspector.stats() or {},
            "total_tasks": len(celery_app.tasks),
            "ping": inspector.ping() or {},
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to get worker status: {str(e)}")
