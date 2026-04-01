"""Task module for Rhesis backend."""

import logging
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from rhesis.backend.celery.core import app
from rhesis.backend.notifications import email_service

# Import all task modules to ensure they're registered with Celery
from rhesis.backend.tasks import (
    example_task,  # noqa: F401
    execution,  # noqa: F401
    task_notifications,  # noqa: F401
    test_configuration,  # noqa: F401
    test_set,  # noqa: F401
)
from rhesis.backend.tasks.base import (
    BaseTask,
    EmailEnabledTask,
    SilentTask,
    email_notification,
)
from rhesis.backend.tasks.enums import (
    DEFAULT_METRIC_WORKERS,
    DEFAULT_RESULT_STATUS,
    DEFAULT_RUN_STATUS_COMPLETED,
    DEFAULT_RUN_STATUS_FAILED,
    DEFAULT_RUN_STATUS_PROGRESS,
    TestType,
)

# Import task functions after BaseTask is defined to avoid circular imports
from rhesis.backend.tasks.example_task import (
    echo,
    email_notification_test,
    get_test_configuration,
    get_test_set_count,
    manual_db_example,
    process_data,
)
from rhesis.backend.tasks.execution.results import collect_results
from rhesis.backend.tasks.test_configuration import execute_test_configuration
from rhesis.backend.tasks.test_set import count_test_sets
from rhesis.backend.tasks.utils import increment_test_run_progress

logger = logging.getLogger(__name__)

# Type variable for task functions
T = TypeVar("T", bound=Callable)

__all__ = [
    # Core task system
    "app",
    # Classes
    "BaseTask",
    "EmailEnabledTask",
    "SilentTask",
    # Decorators
    "email_notification",
    # Helper functions
    "task_launcher",
    "increment_test_run_progress",
    # Services
    "email_service",
    # Tasks
    "echo",
    "count_test_sets",
    "execute_test_configuration",
    "collect_results",
    "get_test_configuration",
    "get_test_set_count",
    "manual_db_example",
    "email_notification_test",
    "process_data",
    # Constants
    "DEFAULT_METRIC_WORKERS",
    "DEFAULT_RESULT_STATUS",
    "DEFAULT_RUN_STATUS_PROGRESS",
    "DEFAULT_RUN_STATUS_COMPLETED",
    "DEFAULT_RUN_STATUS_FAILED",
]


def task_launcher(task: T, *args: Any, current_user=None, task_id: Optional[str] = None, **kwargs: Any):
    """
    Launch a task with proper context from a FastAPI route.

    This helper automatically adds organization_id and user_id from current_user
    to the task context, removing the need to pass them explicitly.

    Args:
        task: The Celery task to launch
        *args: Positional arguments to pass to the task
        current_user: User object from FastAPI dependency (must have id and organization_id)
        task_id: Optional pre-generated Celery task ID.  Pass a UUID string to
            ensure the task is dispatched under a known ID so the caller can
            persist it before the worker starts.
        **kwargs: Keyword arguments to pass to the task

    Returns:
        The AsyncResult from the launched task
    """
    # Prepare headers for tenant context (these won't interfere with task function signatures)
    headers = {}
    if current_user is not None:
        if hasattr(current_user, "id") and current_user.id is not None:
            headers["user_id"] = str(current_user.id)

        if hasattr(current_user, "organization_id") and current_user.organization_id is not None:
            headers["organization_id"] = str(current_user.organization_id)

    apply_kwargs: Dict[str, Any] = dict(args=args, kwargs=kwargs)
    if headers:
        apply_kwargs["headers"] = headers
    if task_id:
        apply_kwargs["task_id"] = task_id

    if apply_kwargs.get("headers") or apply_kwargs.get("task_id"):
        return task.apply_async(**apply_kwargs)
    else:
        return task.delay(*args, **kwargs)
