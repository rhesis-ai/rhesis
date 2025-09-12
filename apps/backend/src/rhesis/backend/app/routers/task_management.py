import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.services.task_notification_service import send_task_assignment_notification
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Use rhesis logger
from rhesis.backend.logging import logger

# Create the detailed schema for Task
TaskDetailSchema = create_detailed_schema(schemas.Task, models.Task)


def _send_task_assignment_email(task_id: str, frontend_url: str = None, db: Session = None):
    """
    Send task assignment email.
    """
    try:
        if db:
            from rhesis.backend.app import models

            task = db.query(models.Task).filter(models.Task.id == task_id).first()
            if task and task.assignee_id:
                success = send_task_assignment_notification(
                    db=db, task=task, frontend_url=frontend_url
                )
                if success:
                    logger.info(f"Task assignment email sent successfully for task {task_id}")
                    return True
                else:
                    logger.error(f"Task assignment email failed for task {task_id}")
                    return False
            else:
                logger.warning(f"Task {task_id} not found or has no assignee")
                return False
        else:
            logger.error("No database session provided for email sending")
            return False
    except Exception as error:
        logger.error(f"Email sending failed for task {task_id}: {error}")
        return False


router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Task)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db)):
    """Create a new task"""
    try:
        created_task = crud.create_task(db=db, task=task)

        # Send email notification if task has an assignee
        if created_task.assignee_id:
            frontend_url = os.getenv("FRONTEND_URL")
            _send_task_assignment_email(
                task_id=str(created_task.id), frontend_url=frontend_url, db=db
            )

        return created_task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle database constraint violations
        error_msg = str(e)
        if (
            "foreign key constraint" in error_msg.lower()
            or "violates foreign key" in error_msg.lower()
        ):
            raise HTTPException(status_code=400, detail="Invalid reference in task data")
        if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Task with this title already exists")
        # Re-raise other database errors as 500
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=list[TaskDetailSchema])
@with_count_header(model=models.Task)
def list_tasks(
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """List tasks with filtering, sorting, and comment counts"""
    try:
        return crud.get_tasks_with_comment_counts(
            db=db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter
        )
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{task_id}", response_model=TaskDetailSchema)
def get_task(task_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a single task by ID"""
    task = crud.get_task(db=db, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{entity_type}/{entity_id}", response_model=list[TaskDetailSchema])
@with_count_header(model=models.Task)
def get_tasks_by_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Get tasks by entity type and entity ID"""
    try:
        # Create a filter expression for entity_type and entity_id
        filter_expr = f"entity_type eq '{entity_type}' and entity_id eq {entity_id}"

        return crud.get_tasks(
            db=db,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter_expr,
        )
    except Exception as e:
        logger.error(f"Error getting tasks by entity {entity_type}/{entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{task_id}", response_model=schemas.Task)
def update_task(task_id: uuid.UUID, task: schemas.TaskUpdate, db: Session = Depends(get_db)):
    """Update a task"""
    try:
        # Get the current task to check for assignee changes
        current_task = crud.get_task(db=db, task_id=task_id)
        if current_task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        # Check if assignee is being changed
        assignee_changed = (
            task.assignee_id is not None and task.assignee_id != current_task.assignee_id
        )

        updated_task = crud.update_task(db=db, task_id=task_id, task=task)
        if updated_task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        # Send email notification if assignee was changed to a new user
        if assignee_changed and updated_task.assignee_id:
            frontend_url = os.getenv("FRONTEND_URL")
            _send_task_assignment_email(
                task_id=str(updated_task.id), frontend_url=frontend_url, db=db
            )

        return updated_task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        if (
            "foreign key constraint" in error_msg.lower()
            or "violates foreign key" in error_msg.lower()
        ):
            raise HTTPException(status_code=400, detail="Invalid reference in task data")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{task_id}")
def delete_task(task_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a task"""
    try:
        success = crud.delete_task(db=db, task_id=task_id)
        if not success:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"message": "Task deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
