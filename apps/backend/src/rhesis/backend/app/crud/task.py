"""CRUD operations for tasks.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.

``get_task`` and ``get_tasks`` pass ``selectin_chains=[["comments"]]`` explicitly.
``Task.comments`` is a custom polymorphic relationship (``viewonly``, matched on
``Comment.entity_id`` plus ``entity_type == "Task"``), not one of the CommentsMixin
comments/tasks/files/tags defaults that the loader picks up on its own -- and
``schemas.Task.comment_count`` reads it, so without the chain every task in a response
triggers its own lazy load.

``create_task`` and ``update_task`` own the ``completed_at`` timestamp: it is stamped when
the task's status is, or becomes, the one named "Completed". ``update_task`` re-reads both
the current task and the incoming status with explicit ``organization_id`` filters instead
of relying on the ambient scope, so a ``status_id`` belonging to another organization
cannot drive the completion timestamp.

Task and Comment are linked in two independent directions, and only one of them shows up
here. The comments attached *to* a task (``Comment.entity_type == "Task"``, ``entity_id ==
task.id``) are what ``Task.comments`` holds and what the ``selectin_chains`` above load.
The other direction -- a task created *from* a comment, which records the comment on
``Task.task_metadata["comment_id"]`` -- is cleaned up in ``crud/comment.py``: its
``delete_comment`` strips that key out of every referencing task, so deleting a comment
leaves no orphaned reference behind.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item_detail,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import include

# Relationships serialized by schemas.TaskDetail -- user, assignee, status, priority.
_TASK_RELATED_FIELDS = (
    include(models.Task.user),
    include(models.Task.assignee),
    include(models.Task.status),
    include(models.Task.priority),
)


def get_task(
    db: Session, task_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Task]:
    """Get task with relationships eagerly loaded."""
    # Task.comments is a custom polymorphic relationship (viewonly, matched by
    # entity_id/entity_type), not the CommentsMixin comments/tasks/files/tags
    # default -- TaskDetail.comment_count reads it directly, so it needs its
    # own explicit selectin_chains entry.
    return get_item_detail(
        db,
        models.Task,
        task_id,
        organization_id,
        user_id,
        related_fields=_TASK_RELATED_FIELDS,
        selectin_chains=[["comments"]],
    )


def get_tasks(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Task]:
    """Get tasks with filtering and sorting"""
    # See get_task -- Task.comments is a custom polymorphic relationship, not
    # covered by the CommentsMixin default, but TaskDetail.comment_count reads it.
    return get_items_detail(
        db,
        models.Task,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_TASK_RELATED_FIELDS,
        selectin_chains=[["comments"]],
        organization_id=organization_id,
        user_id=user_id,
    )


def create_task(
    db: Session, task: schemas.TaskCreate, organization_id: str = None, user_id: str = None
) -> models.Task:
    """Create a new task"""
    # Check if task is being created with "Completed" status
    if task.status_id is not None:
        status = db.query(models.Status).filter(models.Status.id == task.status_id).first()
        if status and status.name == "Completed":
            # Set completed_at to current timestamp
            task.completed_at = datetime.now(timezone.utc)

    return create_item(db, models.Task, task, organization_id=organization_id, user_id=user_id)


def update_task(
    db: Session,
    task_id: uuid.UUID,
    task: schemas.TaskUpdate,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Task]:
    """Update a task with organization filtering"""
    # Check if status is being changed to "Completed"
    if task.status_id is not None:
        # Get current task to compare status (SECURITY CRITICAL)
        task_query = db.query(models.Task).filter(models.Task.id == task_id)
        if organization_id:
            task_query = task_query.filter(
                models.Task.organization_id == uuid.UUID(organization_id)
            )

        current_task = task_query.first()
        if current_task and task.status_id != current_task.status_id:
            # Get the new status with organization filtering (SECURITY CRITICAL)
            status_query = db.query(models.Status).filter(models.Status.id == task.status_id)
            if organization_id:
                status_query = status_query.filter(
                    models.Status.organization_id == uuid.UUID(organization_id)
                )

            new_status = status_query.first()
            if new_status and new_status.name == "Completed":
                # Set completed_at to current timestamp
                task.completed_at = datetime.now(timezone.utc)

    return update_item(
        db, models.Task, task_id, task, organization_id=organization_id, user_id=user_id
    )


def delete_task(db: Session, task_id: uuid.UUID, organization_id: str, user_id: str) -> bool:
    """Delete a task"""
    result = delete_item(db, models.Task, task_id, organization_id=organization_id, user_id=user_id)
    return result is not None
