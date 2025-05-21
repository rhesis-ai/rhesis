"""Enum definitions and constants used by tasks throughout the application."""

from enum import Enum

# Metrics constants
DEFAULT_METRIC_WORKERS = 5


class ResultStatus(str, Enum):
    """Enum for test result statuses."""
    PASS = "Pass"
    FAIL = "Fail"


class RunStatus(str, Enum):
    """Enum for test run statuses."""
    PROGRESS = "Progress"
    COMPLETED = "Completed"
    FAILED = "Failed" 