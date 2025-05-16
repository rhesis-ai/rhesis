"""Task module for Rhesis backend."""

from celery import Task


class BaseTask(Task):
    """Base task class with retry settings."""

    autoretry_for = (Exception,)
    max_retries = 3
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


# Import task functions after BaseTask is defined to avoid circular imports
# We use direct imports instead of relative imports to be explicit
from rhesis.backend.tasks.example_task import echo, process_data  # noqa: E402
from rhesis.backend.tasks.test_configuration import execute_test_configuration  # noqa: E402
from rhesis.backend.tasks.test_set import count_test_sets  # noqa: E402

__all__ = [
    "BaseTask",
    "process_data",
    "echo",
    "count_test_sets",
    "execute_test_configuration",
]
