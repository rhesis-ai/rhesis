"""
Background tasks for task-related email notifications.
"""

from typing import Optional
from uuid import UUID

from rhesis.backend.app import models
from rhesis.backend.app.database import get_db
from rhesis.backend.app.services.task_notification import send_task_assignment_notification
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.base import BaseTask


class SendTaskAssignmentEmailTask(BaseTask):
    """Background task for sending task assignment email notifications."""

    name = "send_task_assignment_email"
    display_name = "Send Task Assignment Email"

    def run(self, task_id: str, frontend_url: Optional[str] = None):
        """
        Send task assignment email notification.

        Args:
            task_id: UUID string of the task
            frontend_url: Optional frontend URL for task links
        """
        try:
            with get_db() as db:
                # Get the task
                task = db.query(models.Task).filter(models.Task.id == UUID(task_id)).first()
                if not task:
                    logger.error(f"Task not found: {task_id}")
                    return False

                # Check if task has an assignee
                if not task.assignee_id:
                    logger.warning(f"Task {task_id} has no assignee, skipping email notification")
                    return False

                # Send the email notification
                success = send_task_assignment_notification(
                    db=db, task=task, frontend_url=frontend_url
                )

                if success:
                    logger.info(f"Task assignment email sent for task {task_id}")
                else:
                    logger.error(f"Failed to send task assignment email for task {task_id}")

                return success

        except Exception as e:
            logger.error(f"Error in SendTaskAssignmentEmailTask for task {task_id}: {str(e)}")
            raise


# Create task instance
send_task_assignment_email_task = SendTaskAssignmentEmailTask()
