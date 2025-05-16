from celery import Task


class BaseTask(Task):
    """Base task class with retry settings."""

    # Automatically retry on any exception
    autoretry_for = (Exception,)

    # Maximum number of retries
    max_retries = 3

    # Exponential backoff: 1min, 5min, 25min
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes max delay

    # Report started status
    track_started = True
