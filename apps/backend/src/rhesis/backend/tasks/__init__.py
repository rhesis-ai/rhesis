"""Task module for Rhesis backend."""

from typing import Any, Callable, Dict, Optional, TypeVar, Union

from rhesis.backend.tasks.base import BaseTask, EmailEnabledTask, SilentTask, with_tenant_context
from rhesis.backend.tasks.enums import (
    DEFAULT_METRIC_WORKERS,
    DEFAULT_RESULT_STATUS,
    DEFAULT_RUN_STATUS_PROGRESS,
    DEFAULT_RUN_STATUS_COMPLETED,
    DEFAULT_RUN_STATUS_FAILED
)
from rhesis.backend.tasks.utils import increment_test_run_progress
from rhesis.backend.tasks.email_service import email_service

# Import task functions after BaseTask is defined to avoid circular imports
# We use direct imports instead of relative imports to be explicit
from rhesis.backend.tasks.example_task import echo, get_test_configuration, get_test_set_count, manual_db_example, email_notification_test  # noqa: E402
from rhesis.backend.tasks.test_configuration import execute_test_configuration  # noqa: E402
from rhesis.backend.tasks.test_set import count_test_sets  # noqa: E402

# Import all tasks
# Make sure to import any implemented tasks here to ensure they're discovered
from rhesis.backend.tasks import test_configuration
from rhesis.backend.tasks import test_set

# Type variable for task functions
T = TypeVar('T', bound=Callable)

# Import so tasks are properly registered with Celery
from rhesis.backend.tasks import example_task  # noqa

__all__ = [
    # Classes
    "BaseTask",
    "EmailEnabledTask",
    "SilentTask",
    
    # Decorators
    "with_tenant_context",
    
    # Helper functions
    "task_launcher",
    "increment_test_run_progress",
    
    # Services
    "email_service",
    
    # Tasks
    "echo",
    "count_test_sets",
    "execute_test_configuration",
    "get_test_configuration",
    "get_test_set_count",
    "manual_db_example",
    "email_notification_test",
    
    # Constants
    "DEFAULT_METRIC_WORKERS",
    "DEFAULT_RESULT_STATUS",
    "DEFAULT_RUN_STATUS_PROGRESS",
    "DEFAULT_RUN_STATUS_COMPLETED",
    "DEFAULT_RUN_STATUS_FAILED",
]

def task_launcher(task: T, *args: Any, current_user=None, **kwargs: Any):
    """
    Launch a task with proper context from a FastAPI route.
    
    This helper automatically adds organization_id and user_id from current_user
    to the task context, removing the need to pass them explicitly.
    
    Uses task.delay() for reliable async task submission that works across all environments.
    
    Args:
        task: The Celery task to launch
        *args: Positional arguments to pass to the task
        current_user: User object from FastAPI dependency (must have id and organization_id)
        **kwargs: Keyword arguments to pass to the task
        
    Returns:
        The AsyncResult from the launched task
        
    Examples:
        # Basic usage with FastAPI dependency
        @router.post("/endpoint")
        def endpoint(current_user = Depends(get_current_user)):
            result = task_launcher(my_task, arg1, arg2, current_user=current_user)
            return {"task_id": result.id}
            
        # With a decorated task that uses with_tenant_context
        @router.post("/{test_configuration_id}/execute")
        def execute_endpoint(
            test_configuration_id: UUID,
            current_user: schemas.User = Depends(require_current_user_or_token)
        ):
            task = task_launcher(
                execute_test_configuration, 
                str(test_configuration_id),
                current_user=current_user
            )
            return {"task_id": task.id}
    """
    # Add user context to kwargs (these will be moved to headers by before_start)
    if current_user is not None:
        if hasattr(current_user, 'id') and current_user.id is not None:
            kwargs.setdefault('user_id', str(current_user.id))
        
        if hasattr(current_user, 'organization_id') and current_user.organization_id is not None:
            kwargs.setdefault('organization_id', str(current_user.organization_id))
    
    # Use delay() which is Celery's standard method for async task submission
    # This avoids ChannelPromise issues and works reliably across all environments
    return task.delay(*args, **kwargs)
