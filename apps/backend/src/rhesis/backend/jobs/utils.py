"""
Utility functions for background job operations and common patterns.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.test_run import get_test_runs
from rhesis.backend.app.utils.uuid_utils import safe_uuid_convert
from rhesis.backend.jobs.enums import RunStatus

logger = logging.getLogger(__name__)


def get_test_run_by_config(
    db: Session, test_configuration_id: str, limit: int = 1
) -> Optional[Any]:
    """
    Get the most recent test run for a test configuration.

    Args:
        db: Database session
        test_configuration_id: Test configuration ID
        limit: Maximum number of results to return

    Returns:
        Most recent test run or None if not found
    """
    try:
        test_runs = get_test_runs(
            db,
            limit=limit,
            filter=f"test_configuration_id eq {test_configuration_id}",
            sort_by="created_at",
            sort_order="desc",
        )
        return test_runs[0] if test_runs else None
    except Exception:
        return None


def get_test_run_by_task_id(
    db: Session, task_id: str, organization_id: str = None
) -> Optional[Any]:
    """Find the test run whose ``attributes->>'task_id'`` equals *task_id*.

    Uses a SQL-level JSONB filter instead of loading rows into Python.
    """
    from rhesis.backend.app.models.test_run import TestRun

    try:
        query = db.query(TestRun).filter(TestRun.attributes["task_id"].astext == task_id)
        if organization_id:
            query = query.filter(TestRun.organization_id == organization_id)
        return query.first()
    except Exception:
        return None


def create_task_result(
    task_id: str, test_config_id: str, test_run_id: Optional[str] = None, **extra_data
) -> Dict[str, Any]:
    """
    Create a standardized task result dictionary.

    Args:
        task_id: Task identifier
        test_config_id: Test configuration ID
        test_run_id: Test run ID (optional)
        **extra_data: Additional data to include

    Returns:
        Standardized result dictionary
    """
    result = {"task_id": task_id, "test_configuration_id": test_config_id, **extra_data}

    if test_run_id:
        result["test_run_id"] = test_run_id

    return result


def update_test_run_with_error(
    db: Session, test_run: Any, error_message: str, status: str = RunStatus.FAILED.value
) -> bool:
    """
    Update a test run with error information.

    Args:
        db: Database session
        test_run: Test run object
        error_message: Error message to record
        status: Status to set (defaults to FAILED)

    Returns:
        True if update succeeded, False otherwise
    """
    try:
        from rhesis.backend.jobs.execution.run import update_test_run_status

        update_test_run_status(db, test_run, status, error_message)
        return True
    except Exception:
        return False


def format_context_info(org_id: Optional[str], user_id: Optional[str]) -> Dict[str, str]:
    """
    Format organization and user context into a standardized dictionary.

    Args:
        org_id: Organization ID
        user_id: User ID

    Returns:
        Dictionary with formatted context information
    """
    return {"organization_id": org_id or "unknown", "user_id": user_id or "unknown"}


def validate_task_parameters(**params) -> Tuple[bool, Optional[str]]:
    """
    Validate common task parameters.

    Args:
        **params: Parameters to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_ids = ["test_configuration_id", "test_run_id", "test_id"]

    for param_name, param_value in params.items():
        if param_name in required_ids:
            if not param_value:
                return False, f"Missing required parameter: {param_name}"

            # Validate UUID format for ID parameters
            if param_name.endswith("_id"):
                uuid_val = safe_uuid_convert(param_value)
                if uuid_val is None:
                    return False, f"Invalid UUID format for {param_name}: {param_value}"

    return True, None


def format_execution_time(duration_seconds: float) -> str:
    """
    Format execution time in a user-friendly way.

    Args:
        duration_seconds: Duration in seconds (can be float)

    Returns:
        str: Formatted duration string

    Examples:
        - 45.2 seconds -> "45.2 seconds"
        - 125.0 seconds -> "2.1 minutes"
        - 3665.5 seconds -> "61.1 minutes"
    """
    if duration_seconds >= 60:
        minutes = duration_seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        return f"{duration_seconds:.1f} seconds"


def format_execution_time_from_ms(duration_ms: int) -> str:
    """
    Format execution time from milliseconds in a user-friendly way.

    Args:
        duration_ms: Duration in milliseconds

    Returns:
        str: Formatted duration string

    Examples:
        - 45200 ms -> "45.2 seconds"
        - 125000 ms -> "2.1 minutes"
    """
    duration_seconds = duration_ms / 1000
    return format_execution_time(duration_seconds)


# Execution mode utilities have been moved to rhesis.backend.jobs.execution.modes
# Import them from there for backwards compatibility if needed
