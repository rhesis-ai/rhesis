"""
Shared utilities for test execution modes.

This module contains common logic used by both parallel and sequential execution
to ensure consistent behavior and results.
"""

from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import ExecutionMode
from rhesis.backend.tasks.execution.results import collect_results
from rhesis.backend.tasks.utils import increment_test_run_progress


def update_test_run_start(
    session: Session, 
    test_run: TestRun, 
    execution_mode: ExecutionMode,
    total_tests: int,
    start_time: datetime,
    **extra_attributes
) -> None:
    """
    Update test run with start information.
    
    Args:
        session: Database session
        test_run: TestRun object
        execution_mode: ExecutionMode enum
        total_tests: Total number of tests
        start_time: Execution start time
        **extra_attributes: Additional attributes to set
    """
    attributes = test_run.attributes.copy() if test_run.attributes else {}
    attributes.update({
        "execution_mode": execution_mode.value,
        "started_at": start_time.isoformat(),
        "total_tests": total_tests,
        "updated_at": datetime.utcnow().isoformat(),
        **extra_attributes
    })
    
    crud.update_test_run(session, test_run.id, crud.schemas.TestRunUpdate(attributes=attributes))


def store_test_result(
    session: Session,
    test_run_id: str,
    test_id: str,
    result: Dict[str, Any]
) -> None:
    """
    Store an individual test result and update test run progress.
    
    This ensures sequential execution creates the same database records
    as parallel execution for consistent result processing.
    
    Args:
        session: Database session
        test_run_id: Test run ID
        test_id: Test ID
        result: Test result dictionary
    """
    try:
        # Determine if test was successful
        was_successful = (
            result.get("status") not in ["failed", "error"] and
            result.get("error") is None
        )
        
        # Update test run progress (this updates completed_tests/failed_tests attributes)
        increment_test_run_progress(
            db=session,
            test_run_id=test_run_id,
            test_id=test_id,
            was_successful=was_successful
        )
        
        logger.debug(f"Updated test run progress for test {test_id}, successful: {was_successful}")
        
    except Exception as e:
        logger.error(f"Failed to store test result for test {test_id}: {str(e)}")


def create_execution_result(
    test_run: TestRun,
    test_config: TestConfiguration,
    total_tests: int,
    execution_mode: ExecutionMode,
    **extra_data
) -> Dict[str, Any]:
    """
    Create a standardized execution result dictionary.
    
    Args:
        test_run: TestRun object
        test_config: TestConfiguration object
        total_tests: Total number of tests
        execution_mode: ExecutionMode enum
        **extra_data: Additional data to include
        
    Returns:
        Standardized result dictionary
    """
    result = {
        "test_run_id": str(test_run.id),
        "test_configuration_id": str(test_config.id),
        "test_set_id": str(test_config.test_set_id),
        "total_tests": total_tests,
        "execution_mode": execution_mode.value,
        **extra_data
    }
    
    return result


def trigger_results_collection(
    test_config: TestConfiguration,
    test_run_id: str,
    results: List[Dict[str, Any]]
) -> Any:
    """
    Trigger results collection as a Celery task.
    
    This ensures sequential execution gets the same result processing
    as parallel execution, including email notifications.
    
    Args:
        test_config: TestConfiguration object
        test_run_id: Test run ID
        results: List of test results
        
    Returns:
        Celery task result
    """
    logger.info(f"Triggering results collection for test run {test_run_id}")
    
    # Create the collect_results task
    # Note: For chord callbacks, results are passed automatically by Celery
    # For manual calls, we need to pass them explicitly
    task = collect_results.s(
        results,  # This will be the first parameter (results)
        test_run_id  # This will be the second parameter (test_run_id)
    ).set(
        # Pass context in headers so BaseTask.before_start can pick them up
        headers={
            'organization_id': str(test_config.organization_id) if test_config.organization_id else None,
            'user_id': str(test_config.user_id) if test_config.user_id else None,
        }
    )
    
    # Execute the task
    return task.apply_async()


def create_failure_result(test_id: str, error: Exception) -> Dict[str, Any]:
    """
    Create a standardized failure result.
    
    Args:
        test_id: Test ID that failed
        error: Exception that occurred
        
    Returns:
        Failure result dictionary
    """
    return {
        "test_id": test_id,
        "status": "failed",
        "error": str(error),
        "execution_time": 0,
        "exception_type": type(error).__name__
    } 