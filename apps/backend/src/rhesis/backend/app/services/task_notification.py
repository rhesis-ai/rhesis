"""
Service for sending task assignment email notifications.
"""

from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud import get_status, get_type_lookup, get_user
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.notifications import EmailTemplate, email_service


def send_task_assignment_notification(
    db: Session, task: models.Task, frontend_url: Optional[str] = None
) -> bool:
    """
    Send email notification when a task is assigned to a user.

    Args:
        db: Database session
        task: Task model instance
        frontend_url: Optional frontend URL for task links

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        # Get assignee details
        assignee = get_user(db, task.assignee_id) if task.assignee_id else None

        if not assignee or not assignee.email:
            logger.warning(
                f"Cannot send task assignment email: assignee not found or no email for task {task.id}"
            )
            return False

        # Get creator details
        creator = get_user(db, task.user_id) if task.user_id else None

        # Get status details
        status = get_status(db, task.status_id) if task.status_id else None

        # Get priority details
        priority = get_type_lookup(db, task.priority_id) if task.priority_id else None

        # Get entity name if entity_type and entity_id are provided
        entity_name = None
        if task.entity_type and task.entity_id:
            # SECURITY: Pass task's organization_id for filtering
            entity_name = _get_entity_name(
                db, task.entity_type, task.entity_id, str(task.organization_id)
            )
            # Ensure we don't pass "N/A" or None as entity_name
            if entity_name in [None, "N/A", "None"]:
                entity_name = None

        # Prepare template variables
        template_variables = {
            "assignee_name": assignee.name or assignee.given_name or "User",
            "assigner_name": creator.name or creator.given_name if creator else "Team Member",
            "task_title": task.title,
            "task_description": task.description,
            "task_id": str(task.id),
            "status_name": status.name if status else "Unknown",
            "priority_name": priority.type_value if priority else None,
            "entity_type": task.entity_type,
            "entity_id": str(task.entity_id) if task.entity_id else None,
            "entity_name": entity_name,
            "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if task.created_at
            else "N/A",
            "task_metadata": task.task_metadata or {},
            "frontend_url": frontend_url,
        }

        # Check email service configuration

        # Send email

        success = email_service.send_email(
            template=EmailTemplate.TASK_ASSIGNMENT,
            recipient_email=assignee.email,  # Use actual assignee email instead of hardcoded
            subject=f"New Task Assignment: {task.title}",
            template_variables=template_variables,
            task_id=str(task.id),
        )

        if success:
            logger.info(
                f"Task assignment email sent successfully to {assignee.email} for task {task.id}"
            )
        else:
            logger.error(
                f"Failed to send task assignment email to {assignee.email} for task {task.id}"
            )

        return success

    except Exception as e:
        logger.error(f"Error sending task assignment email for task {task.id}: {str(e)}")
        return False


def _get_entity_name(
    db: Session, entity_type: str, entity_id: str, organization_id: str = None
) -> Optional[str]:
    """
    Get the name of an entity based on its type and ID with organization filtering.

    Args:
        db: Database session
        entity_type: Type of entity (Test, TestSet, TestRun, etc.)
        entity_id: ID of the entity
        organization_id: Organization ID for security filtering (CRITICAL)

    Returns:
        Optional[str]: Entity name if found, None otherwise
    """
    try:
        from uuid import UUID

        if entity_type == "Test":
            query = db.query(models.Test).filter(models.Test.id == entity_id)
            if organization_id:
                query = query.filter(models.Test.organization_id == UUID(organization_id))
            test = query.first()
            return test.name if test else None
        elif entity_type == "TestSet":
            query = db.query(models.TestSet).filter(models.TestSet.id == entity_id)
            if organization_id:
                query = query.filter(models.TestSet.organization_id == UUID(organization_id))
            test_set = query.first()
            return test_set.name if test_set else None
        elif entity_type == "TestRun":
            query = db.query(models.TestRun).filter(models.TestRun.id == entity_id)
            if organization_id:
                query = query.filter(models.TestRun.organization_id == UUID(organization_id))
            test_run = query.first()
            return test_run.name if test_run else None
        # Add more entity types as needed
        else:
            logger.warning(f"Unknown entity type for task assignment: {entity_type}")
            return None
    except Exception as e:
        logger.error(f"Error getting entity name for {entity_type} {entity_id}: {str(e)}")
        return None
