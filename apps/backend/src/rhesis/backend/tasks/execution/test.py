"""
Individual test execution task for Celery workers.

This module provides the Celery task wrapper for executing individual tests,
handling model selection, result validation, and progress tracking.
"""

from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.utils.user_model_utils import get_user_evaluation_model
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.base import SilentTask
from rhesis.backend.tasks.execution.test_execution import execute_test
from rhesis.backend.tasks.utils import increment_test_run_progress
from rhesis.backend.worker import app

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def resolve_tenant_context(
    task_request, user_id: Optional[str], organization_id: Optional[str]
) -> Tuple[str, str]:
    """
    Resolve tenant context from task parameters and request headers.

    Args:
        task_request: Celery task request object
        user_id: User ID from kwargs
        organization_id: Organization ID from kwargs

    Returns:
        Tuple of (user_id, organization_id)
    """
    request_user_id = getattr(task_request, "user_id", None)
    request_org_id = getattr(task_request, "organization_id", None)

    # Use passed parameters if available, otherwise use request context
    resolved_user_id = user_id or request_user_id
    resolved_org_id = organization_id or request_org_id

    return resolved_user_id, resolved_org_id


def get_evaluation_model(db: Session, user_id: str) -> Any:
    """
    Get the evaluation model for the user, with fallback to default.

    Args:
        db: Database session
        user_id: User ID string

    Returns:
        Model instance (string or BaseLLM)
    """
    try:
        user = crud.get_user_by_id(db, user_id)
        if user:
            return get_user_evaluation_model(db, user)
        else:
            logger.warning(
                f"[MODEL_SELECTION] User {user_id} not found, using default: "
                f"{DEFAULT_GENERATION_MODEL}"
            )
            return DEFAULT_GENERATION_MODEL
    except Exception as e:
        logger.warning(
            f"[MODEL_SELECTION] Error fetching user model: {str(e)}, "
            f"using default: {DEFAULT_GENERATION_MODEL}"
        )
        return DEFAULT_GENERATION_MODEL


def validate_and_normalize_result(result: Any, test_id: str) -> Dict[str, Any]:
    """
    Validate and normalize test execution result.

    Ensures the result is always a valid dict, even if execute_test returns
    None or an invalid type.

    Args:
        result: Result from execute_test
        test_id: Test ID for logging

    Returns:
        Valid result dict
    """
    # Validate result
    if result is None:
        logger.error(f"execute_test returned None for test {test_id}")
        return {
            "test_id": test_id,
            "status": "failed",
            "error": "execute_test returned None - this indicates a bug",
            "execution_time": 0,
        }

    if not isinstance(result, dict):
        logger.error(f"execute_test returned non-dict type {type(result)} for test {test_id}")
        return {
            "test_id": test_id,
            "status": "failed",
            "error": f"execute_test returned non-dict type: {type(result)}",
            "execution_time": 0,
            "original_result": str(result),
        }

    # Validate required fields
    required_fields = ["test_id", "execution_time"]
    missing_fields = [field for field in required_fields if field not in result]
    if missing_fields:
        logger.warning(f"Result missing required fields {missing_fields} for test {test_id}")

    return result


def update_progress(
    test_run_id: str,
    test_id: str,
    result: Dict[str, Any],
    organization_id: str,
    user_id: str,
) -> None:
    """
    Update test run progress based on execution result.

    Args:
        test_run_id: Test run ID
        test_id: Test ID
        result: Execution result
        organization_id: Organization ID
        user_id: User ID
    """
    was_successful = (
        isinstance(result, dict) and result.get("status") != "failed" and result is not None
    )

    with get_db_with_tenant_variables(organization_id, user_id) as db:
        progress_updated = increment_test_run_progress(
            db=db,
            test_run_id=test_run_id,
            test_id=test_id,
            was_successful=was_successful,
            organization_id=organization_id,
            user_id=user_id,
        )

    if progress_updated:
        logger.debug(f"Updated test run progress for test {test_id}, successful: {was_successful}")
    else:
        logger.warning(f"Failed to update test run progress for test {test_id}")


def create_failure_result(test_id: str, exception: Exception) -> Dict[str, Any]:
    """
    Create a standardized failure result dict from an exception.

    Args:
        test_id: Test ID
        exception: Exception that occurred

    Returns:
        Failure result dict
    """
    return {
        "test_id": test_id,
        "status": "failed",
        "error": str(exception),
        "execution_time": 0,
        "exception_type": type(exception).__name__,
    }


def handle_retry_or_fail(
    task_self,
    test_id: str,
    exception: Exception,
    failure_result: Dict[str, Any],
    test_config_id: str,
    test_run_id: str,
    endpoint_id: str,
    organization_id: str,
    user_id: str,
    reference_test_run_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Handle task retry logic or return failure result.

    Args:
        task_self: The task instance (self)
        test_id: Test ID
        exception: Exception that occurred
        failure_result: Pre-created failure result dict
        test_config_id: Test configuration ID
        test_run_id: Test run ID
        endpoint_id: Endpoint ID
        organization_id: Organization ID
        user_id: User ID
        reference_test_run_id: Optional previous test run ID for re-scoring
        trace_id: Optional trace ID for trace-based evaluation

    Returns:
        Failure result dict
    """
    if task_self.request.retries < task_self.max_retries:
        logger.warning(
            f"Attempting retry {task_self.request.retries + 1}/"
            f"{task_self.max_retries} for test {test_id}"
        )
        try:
            retry_kwargs = {
                "test_config_id": test_config_id,
                "test_run_id": test_run_id,
                "test_id": test_id,
                "endpoint_id": endpoint_id,
                "organization_id": organization_id,
                "user_id": user_id,
            }
            if reference_test_run_id:
                retry_kwargs["reference_test_run_id"] = reference_test_run_id
            if trace_id:
                retry_kwargs["trace_id"] = trace_id

            task_self.retry(
                exc=exception,
                kwargs=retry_kwargs,
            )
        except task_self.MaxRetriesExceededError:
            logger.error(f"Test {test_id} failed after max retries, returning failure result")
            return failure_result

    logger.error(f"Returning failure result for test {test_id} (no retries left)")
    return failure_result


# ============================================================================
# CELERY TASK
# ============================================================================


@app.task(
    name="rhesis.backend.tasks.execute_single_test",
    base=SilentTask,
    bind=True,
    display_name="Individual Test Execution",
)
def execute_single_test(
    self,
    test_config_id: str,
    test_run_id: str,
    test_id: str,
    endpoint_id: str,
    organization_id: str = None,
    user_id: str = None,
    reference_test_run_id: str = None,
    trace_id: str = None,
):
    """
    Execute a single test and return its results.

    This task orchestrates test execution by:
    1. Resolving tenant context
    2. Fetching the user's evaluation model
    3. Executing the test
    4. Validating and normalizing the result
    5. Updating progress tracking
    6. Handling retries on failure

    Args:
        test_config_id: Test configuration ID
        test_run_id: Test run ID
        test_id: Test ID
        endpoint_id: Endpoint ID to test against
        organization_id: Organization ID for tenant context
        user_id: User ID for tenant context
        reference_test_run_id: Optional previous test run ID for
            re-scoring (loads stored outputs instead of invoking endpoint)
        trace_id: Optional trace ID for trace-based evaluation

    Returns:
        Dict containing test execution results
    """
    # Resolve tenant context from task headers and parameters
    user_id, organization_id = resolve_tenant_context(self.request, user_id, organization_id)

    try:
        # Execute the test with proper tenant context
        with get_db_with_tenant_variables(organization_id, user_id) as db:
            # Get the evaluation model for metrics
            model = get_evaluation_model(db, user_id)

            # Execute the test
            import asyncio

            result = asyncio.run(
                execute_test(
                    db=db,
                    test_config_id=test_config_id,
                    test_run_id=test_run_id,
                    test_id=test_id,
                    endpoint_id=endpoint_id,
                    organization_id=organization_id,
                    user_id=user_id,
                    model=model,
                    reference_test_run_id=reference_test_run_id,
                    trace_id=trace_id,
                )
            )

        # Validate and normalize the result
        result = validate_and_normalize_result(result, test_id)

        # Update test run progress
        update_progress(test_run_id, test_id, result, organization_id, user_id)

        logger.info(f"Test {test_id} execution completed successfully")
        return result

    except Exception as e:
        logger.error(f"Exception in test {test_id} execution: {str(e)}", exc_info=True)

        # Create failure result
        failure_result = create_failure_result(test_id, e)

        # Update progress for failed test
        try:
            update_progress(test_run_id, test_id, failure_result, organization_id, user_id)
        except Exception as progress_error:
            logger.error(f"Failed to update progress for failed test {test_id}: {progress_error}")

        # Handle retry logic or return failure
        return handle_retry_or_fail(
            self,
            test_id,
            e,
            failure_result,
            test_config_id,
            test_run_id,
            endpoint_id,
            organization_id,
            user_id,
            reference_test_run_id=reference_test_run_id,
            trace_id=trace_id,
        )
