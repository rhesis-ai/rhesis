"""Task module for Rhesis backend."""

from typing import Any, Callable, Dict, Optional, TypeVar, Union

from rhesis.backend.logging import logger
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
from rhesis.backend.worker import app

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
    "check_workers_available",
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


def check_workers_available(timeout: float = 2.0) -> bool:
    """
    Check if any Celery workers are available and responding.

    This function pings active workers to ensure tasks can be processed.
    Useful for providing early feedback before submitting tasks.

    Args:
        timeout: Maximum time to wait for worker response in seconds (default: 2.0)

    Returns:
        True if at least one worker is available, False otherwise

    Example:
        >>> if not check_workers_available():
        ...     raise HTTPException(status_code=503, detail="No workers available")
        >>> task = task_launcher(my_task, current_user=user)
    """
    try:
        # Use inspect to check for active workers
        inspect = app.control.inspect(timeout=timeout)
        active_workers = inspect.active()

        # active_workers is None if no workers respond within timeout
        # or a dict of worker_name -> active_tasks if workers respond
        if active_workers is None:
            logger.warning("[WORKER_CHECK] No Celery workers responded within timeout")
            return False

        # Check if we have at least one worker
        worker_count = len(active_workers)
        if worker_count == 0:
            logger.warning("[WORKER_CHECK] No active Celery workers found")
            return False

        logger.info(f"[WORKER_CHECK] Found {worker_count} active Celery worker(s)")
        return True

    except Exception as e:
        logger.error(f"[WORKER_CHECK] Failed to check worker availability: {str(e)}", exc_info=True)
        return False


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

        # With a task that gets tenant context passed directly
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
    # Prepare headers for tenant context (these won't interfere with task function signatures)
    headers = {}
    if current_user is not None:
        if hasattr(current_user, "id") and current_user.id is not None:
            headers["user_id"] = str(current_user.id)

        if hasattr(current_user, "organization_id") and current_user.organization_id is not None:
            headers["organization_id"] = str(current_user.organization_id)

    # Use apply_async with headers to pass tenant context without affecting function signature
    if headers:
        return task.apply_async(args=args, kwargs=kwargs, headers=headers)
    else:
        # Fallback to delay() if no headers
        return task.delay(*args, **kwargs)
