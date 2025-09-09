"""Enum definitions and constants used by tasks throughout the application."""

from enum import Enum

# Metrics constants
DEFAULT_METRIC_WORKERS = 5

# Task status constants
DEFAULT_RESULT_STATUS = "Completed"
DEFAULT_RUN_STATUS_PROGRESS = "Progress"
DEFAULT_RUN_STATUS_COMPLETED = "Completed"
DEFAULT_RUN_STATUS_FAILED = "Failed"

# Task retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_MAX = 600  # 10 minutes
DEFAULT_CHORD_RETRY_MAX = 3
DEFAULT_CHORD_BACKOFF_MAX = 60  # 1 minute


class ResultStatus(str, Enum):
    """Enum for test result statuses."""

    PASS = "Pass"
    FAIL = "Fail"


class RunStatus(str, Enum):
    """Enum for test run statuses."""

    PROGRESS = "Progress"
    COMPLETED = "Completed"
    PARTIAL = "Partial"  # Some tests completed, but some failed
    FAILED = "Failed"


class ExecutionMode(str, Enum):
    """Enum for test execution modes."""

    SEQUENTIAL = "Sequential"
    PARALLEL = "Parallel"
