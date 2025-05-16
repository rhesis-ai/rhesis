from typing import Any, Dict, List

from celery.result import AsyncResult
from fastapi import APIRouter, FastAPI, HTTPException

from rhesis.backend.celery_app import app as celery_app

# Create FastAPI app
fastapi_app = FastAPI(title="Celery Tasks API")

router = APIRouter()


@router.get("/tasks")
async def list_tasks() -> Dict[str, List[str]]:
    """List all registered Celery tasks."""
    # Filter out internal Celery tasks (those starting with "celery.")
    user_tasks = [
        task_name for task_name in celery_app.tasks.keys() if not task_name.startswith("celery.")
    ]
    return {"tasks": sorted(user_tasks)}


@router.get("/tasks/active")
async def list_active_tasks():
    """List all currently running tasks."""
    inspector = celery_app.control.inspect()
    active = inspector.active()
    scheduled = inspector.scheduled()
    reserved = inspector.reserved()

    return {"active": active, "scheduled": scheduled, "reserved": reserved}


@router.get("/tasks/stats")
async def get_stats():
    """Get statistics about the Celery workers and tasks."""
    inspector = celery_app.control.inspect()
    stats = inspector.stats()
    registered = inspector.registered()

    return {"stats": stats, "registered_tasks": registered, "total_tasks": len(celery_app.tasks)}


@router.post("/tasks/{task_name}")
async def create_task(task_name: str, payload: Dict[Any, Any]):
    """Submit a new task to Celery."""
    try:
        # Get the task by name from celery_app
        task = celery_app.tasks[f"rhesis.tasks.{task_name}"]
        # Submit the task
        result = task.delay(**payload)
        return {"task_id": result.id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task {task_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a task."""
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
        "error": str(result.error) if result.failed() else None,
    }


@router.delete("/tasks/{task_id}")
async def revoke_task(task_id: str, terminate: bool = False):
    """Revoke a task (prevent it from being executed if not already running)."""
    celery_app.control.revoke(task_id, terminate=terminate)
    return {"message": f"Task {task_id} revoked"}


@router.get("/health")
async def health_check():
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


@router.get("/workers/status")
async def get_workers_status():
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


@router.get("/tasks/stats")
async def get_task_stats():
    """Get statistics about completed and pending tasks."""
    try:
        i = celery_app.control.inspect()
        stats = i.stats()
        active = i.active()
        scheduled = i.scheduled()
        reserved = i.reserved()

        return {
            "workers": stats,
            "active_tasks": active,
            "scheduled_tasks": scheduled,
            "reserved_tasks": reserved,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to get task stats: {str(e)}")


# Include router in the FastAPI app
fastapi_app.include_router(router, prefix="/api")

# For uvicorn to import
app = fastapi_app
