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

    # Validate assignee is in the same organization
    if task.assignee_id:
        assignee = db.query(models.User).filter(models.User.id == task.assignee_id).first()
        if not assignee:
            raise ValueError("Assignee not found")
        if assignee.organization_id != user_organization_id:
            raise ValueError("Cannot assign task to user from different organization")

    # Validate status is in the same organization
    if task.status_id:
        status = db.query(models.Status).filter(models.Status.id == task.status_id).first()
        if not status:
            raise ValueError("Status not found")
        if status.organization_id != user_organization_id:
            raise ValueError("Status must be from the same organization")

    # Validate priority is in the same organization
    if task.priority_id:
        priority = (
            db.query(models.TypeLookup).filter(models.TypeLookup.id == task.priority_id).first()
        )
        if not priority:
            raise ValueError("Priority not found")
        if priority.organization_id != user_organization_id:
            raise ValueError("Priority must be from the same organization")
