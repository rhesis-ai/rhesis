"""
Utility functions for task operations and common patterns.
"""

from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.tasks.enums import RunStatus


def safe_uuid_convert(value: Any) -> Optional[UUID]:
    """
    Safely convert a value to UUID, returning None if conversion fails.
    
    Args:
        value: Value to convert (string, UUID, or other)
        
    Returns:
        UUID object or None if conversion fails
    """
    if value is None:
        return None
    
    if isinstance(value, UUID):
        return value
    
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def get_test_run_by_config(
    db: Session, 
    test_configuration_id: str, 
    limit: int = 1
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
        test_runs = crud.get_test_runs(
            db,
            limit=limit,
            filter=f"test_configuration_id eq {test_configuration_id}",
            sort_by="created_at",
            sort_order="desc"
        )
        return test_runs[0] if test_runs else None
    except Exception:
        return None


def increment_test_run_progress(
    db: Session, 
    test_run_id: str, 
    test_id: str,
    was_successful: bool = True
) -> bool:
    """
    Atomically increment the completed_tests counter in test run attributes.
    
    This function safely updates the test run progress as individual tests complete,
    providing real-time progress tracking.
    
    Args:
        db: Database session
        test_run_id: Test run UUID
        test_id: Test UUID that was completed
        was_successful: Whether the test was successful or failed
        
    Returns:
        True if update succeeded, False otherwise
    """
    try:
        # Get the test run
        test_run_uuid = safe_uuid_convert(test_run_id)
        if not test_run_uuid:
            return False
            
        test_run = crud.get_test_run(db, test_run_uuid)
        if not test_run:
            return False
        
        # Get current attributes
        current_attributes = test_run.attributes.copy() if test_run.attributes else {}
        
        # Initialize counters if they don't exist
        completed_tests = current_attributes.get("completed_tests", 0)
        failed_tests = current_attributes.get("failed_tests", 0)
        
        # Increment appropriate counter
        if was_successful:
            completed_tests += 1
        else:
            failed_tests += 1
        
        # Update attributes with new progress
        current_attributes.update({
            "completed_tests": completed_tests,
            "failed_tests": failed_tests,
            "last_completed_test_id": test_id,
            "last_update": datetime.utcnow().isoformat(),
            "progress_updated_at": datetime.utcnow().isoformat()
        })
        
        # Update the test run
        update_data = {
            "attributes": current_attributes
        }
        
        crud.update_test_run(db, test_run.id, crud.schemas.TestRunUpdate(**update_data))
        
        return True
        
    except Exception as e:
        # Log error but don't raise - progress update failure shouldn't break test execution
        from rhesis.backend.logging.rhesis_logger import logger
        logger.error(f"Failed to update test run progress: {str(e)}")
        return False


def create_task_result(
    task_id: str,
    test_config_id: str,
    test_run_id: Optional[str] = None,
    **extra_data
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
    result = {
        "task_id": task_id,
        "test_configuration_id": test_config_id,
        **extra_data
    }
    
    if test_run_id:
        result["test_run_id"] = test_run_id
    
    return result


def update_test_run_with_error(
    db: Session,
    test_run: Any,
    error_message: str,
    status: str = RunStatus.FAILED.value
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
        from rhesis.backend.tasks.execution.run import update_test_run_status
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
    return {
        "organization_id": org_id or "unknown",
        "user_id": user_id or "unknown"
    }


def validate_task_parameters(**params) -> Tuple[bool, Optional[str]]:
    """
    Validate common task parameters.
    
    Args:
        **params: Parameters to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_ids = ['test_configuration_id', 'test_run_id', 'test_id']
    
    for param_name, param_value in params.items():
        if param_name in required_ids:
            if not param_value:
                return False, f"Missing required parameter: {param_name}"
            
            # Validate UUID format for ID parameters
            if param_name.endswith('_id'):
                uuid_val = safe_uuid_convert(param_value)
                if uuid_val is None:
                    return False, f"Invalid UUID format for {param_name}: {param_value}"
    
    return True, None


