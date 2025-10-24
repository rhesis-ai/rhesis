"""
Service for task-related business logic and validation.
"""

from sqlalchemy.orm import Session

from rhesis.backend.app import models


def validate_task_organization_constraints(
    db: Session, task, current_user, current_task=None
) -> None:
    """
    Validate organization-level constraints for task assignments.

    Args:
        db: Database session
        task: TaskCreate or TaskUpdate schema
        current_user: Current authenticated user
        current_task: Current task model (for updates)

    Raises:
        ValueError: If organization constraints are violated
    """
    # Get the organization ID from the current user
    user_organization_id = current_user.organization_id

    # Validate assignee is in the same organization (SECURITY CRITICAL)
    if task.assignee_id:
        assignee = (
            db.query(models.User)
            .filter(
                models.User.id == task.assignee_id,
                models.User.organization_id == user_organization_id,
            )
            .first()
        )
        if not assignee:
            raise ValueError("Assignee not found or not in same organization")

    # Validate status is in the same organization (SECURITY CRITICAL)
    if task.status_id:
        status = (
            db.query(models.Status)
            .filter(
                models.Status.id == task.status_id,
                models.Status.organization_id == user_organization_id,
            )
            .first()
        )
        if not status:
            raise ValueError("Status not found or not in same organization")

    # Validate priority is in the same organization (SECURITY CRITICAL)
    if task.priority_id:
        priority = (
            db.query(models.TypeLookup)
            .filter(
                models.TypeLookup.id == task.priority_id,
                models.TypeLookup.organization_id == user_organization_id,
            )
            .first()
        )
        if not priority:
            raise ValueError("Priority not found or not in same organization")
