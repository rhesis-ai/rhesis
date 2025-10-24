import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.services.task_management import validate_task_organization_constraints
from rhesis.backend.app.services.task_notification import send_task_assignment_notification
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Use rhesis logger
from rhesis.backend.logging import logger
from rhesis.backend.telemetry import (
    is_telemetry_enabled,
    set_telemetry_enabled,
    track_feature_usage,
)

# Create the detailed schema for Task
TaskDetailSchema = create_detailed_schema(schemas.Task, models.Task)


router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.post("/", response_model=schemas.Task)
def create_task(
    task: schemas.TaskCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user=Depends(require_current_user_or_token),
):
    """Create a new task"""
    try:
        # Set telemetry context for this request (if telemetry is enabled)
        if is_telemetry_enabled() and current_user:
            set_telemetry_enabled(
                enabled=True,
                user_id=str(current_user.id) if current_user.id else None,
                org_id=str(current_user.organization_id) if current_user.organization_id else None,
            )

        # Validate organization-level constraints
        validate_task_organization_constraints(db, task, current_user)

        created_task = crud.create_task(
            db=db,
            task=task,
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
        )

        # Send email notification if task has an assignee
        if created_task.assignee_id:
            frontend_url = os.getenv("FRONTEND_URL")
            send_task_assignment_notification(db=db, task=created_task, frontend_url=frontend_url)

        # Track feature usage
        track_feature_usage(
            feature_name="task",
            action="created",
            task_id=str(created_task.id),
            entity_type=created_task.entity_type if hasattr(created_task, "entity_type") else None,
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
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    response: Response = None,
):
    """List tasks with filtering, sorting, and comment counts"""
    try:
        organization_id, user_id = tenant_context
        return crud.get_tasks(
            db=db,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
            organization_id=organization_id,
            user_id=user_id,
        )
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{task_id}", response_model=TaskDetailSchema)
def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """Get a single task by ID"""
    organization_id, user_id = tenant_context
    task = crud.get_task(db=db, task_id=task_id, organization_id=organization_id, user_id=user_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # Track feature usage
    track_feature_usage(feature_name="task", action="viewed", task_id=str(task_id))

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
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    response: Response = None,
):
    """Get tasks by entity type and entity ID"""
    try:
        organization_id, user_id = tenant_context
        # Create a filter expression for entity_type and entity_id
        filter_expr = f"entity_type eq '{entity_type}' and entity_id eq {entity_id}"

        return crud.get_tasks(
            db=db,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter_expr,
            organization_id=organization_id,
            user_id=user_id,
        )
    except Exception as e:
        logger.error(f"Error getting tasks by entity {entity_type}/{entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{task_id}", response_model=schemas.Task)
def update_task(
    task_id: uuid.UUID,
    task: schemas.TaskUpdate,
    db: Session = Depends(get_tenant_db_session),
    current_user=Depends(require_current_user_or_token),
):
    """Update a task"""
    try:
        # Set telemetry context for this request (if telemetry is enabled)
        if is_telemetry_enabled() and current_user:
            set_telemetry_enabled(
                enabled=True,
                user_id=str(current_user.id) if current_user.id else None,
                org_id=str(current_user.organization_id) if current_user.organization_id else None,
            )

        organization_id = str(current_user.organization_id)
        user_id = str(current_user.id)

        # Get the current task to check for assignee changes
        current_task = crud.get_task(
            db=db, task_id=task_id, organization_id=organization_id, user_id=user_id
        )
        if current_task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        # Validate organization-level constraints
        validate_task_organization_constraints(db, task, current_user, current_task)

        # Check if assignee is being changed
        assignee_changed = (
            task.assignee_id is not None and task.assignee_id != current_task.assignee_id
        )

        updated_task = crud.update_task(
            db=db, task_id=task_id, task=task, organization_id=organization_id, user_id=user_id
        )
        if updated_task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        # Send email notification if assignee was changed to a new user
        if assignee_changed and updated_task.assignee_id:
            frontend_url = os.getenv("FRONTEND_URL")
            send_task_assignment_notification(db=db, task=updated_task, frontend_url=frontend_url)

        # Track feature usage
        track_feature_usage(
            feature_name="task",
            action="updated",
            task_id=str(task_id),
            fields_updated=list(task.dict(exclude_unset=True).keys()),
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
def delete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """Delete a task"""
    try:
        organization_id, user_id = tenant_context
        success = crud.delete_task(
            db=db, task_id=task_id, organization_id=organization_id, user_id=user_id
        )
        if not success:
            raise HTTPException(status_code=404, detail="Task not found")

        # Track feature usage
        track_feature_usage(feature_name="task", action="deleted", task_id=str(task_id))

        return {"message": "Task deleted successfully"}
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) without modification
        raise
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
