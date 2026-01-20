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
    ERROR = "Error"


class RunStatus(str, Enum):
    """
    Enum for test run statuses.

    Status reflects execution completion, not test assertion results:
    - COMPLETED: All tests executed (regardless of pass/fail results)
    - PARTIAL: Some tests executed, some couldn't (incomplete execution)
    - FAILED: All tests had execution errors (none could execute)
    - PROGRESS: Test run is currently executing
    """

    PROGRESS = "Progress"
    COMPLETED = "Completed"
    PARTIAL = "Partial"
    FAILED = "Failed"


class ExecutionMode(str, Enum):
    """Enum for test execution modes."""

    SEQUENTIAL = "Sequential"
    PARALLEL = "Parallel"


class TestType(str, Enum):
    """
    Enum for test types.

    These are reserved test type values in the TypeLookup table:
    - SINGLE_TURN: Traditional single request-response tests
    - MULTI_TURN: Agentic multi-turn conversation tests using Penelope
    - IMAGE: Image generation/analysis tests
    """

    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"
    IMAGE = "Image"
