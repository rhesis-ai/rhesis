from typing import Optional
from uuid import UUID

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.base import BaseTask, with_tenant_context
from rhesis.backend.tasks.execution.metrics_utils import get_behavior_metrics
from rhesis.backend.tasks.execution.test_execution import execute_test
from rhesis.backend.tasks.utils import increment_test_run_progress
from rhesis.backend.worker import app


@app.task(name="rhesis.backend.tasks.execute_single_test", base=BaseTask, bind=True)
@with_tenant_context
def execute_single_test(
    self,
    test_config_id: str,
    test_run_id: str,
    test_id: str,
    endpoint_id: str,
    organization_id: str = None,  # Make this explicit so it's preserved on retries
    user_id: str = None,          # Make this explicit so it's preserved on retries
    db=None,
):
    """
    Execute a single test and return its results.
    
    This task uses the with_tenant_context decorator to automatically
    handle database sessions with the proper tenant context.
    """
    # Access context from task request - task headers take precedence over kwargs
    task = self.request
    request_user_id = getattr(task, 'user_id', None)
    request_org_id = getattr(task, 'organization_id', None)
    
    # Use passed parameters if available, otherwise use request context
    # This ensures context is preserved during retries
    user_id = user_id or request_user_id
    organization_id = organization_id or request_org_id
    
    logger.info(f"🔍 DEBUG: Starting execute_single_test for test {test_id}")
    logger.debug(f"🔍 DEBUG: Parameters - test_config_id={test_config_id}, test_run_id={test_run_id}, endpoint_id={endpoint_id}")
    logger.debug(f"🔍 DEBUG: Context - user_id={user_id}, organization_id={organization_id}")
    logger.debug(f"🔍 DEBUG: DB session provided: {db is not None}")
    
    try:
        logger.debug(f"🔍 DEBUG: About to call execute_test for test {test_id}")
        
        # Call the main execution function from the dedicated module
        result = execute_test(
            db=db,
            test_config_id=test_config_id,
            test_run_id=test_run_id,
            test_id=test_id,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id
        )
        
        logger.debug(f"🔍 DEBUG: execute_test returned for test {test_id}: {type(result)}")
        
        # Add detailed debugging about the result
        if result is None:
            logger.error(f"🚨 DEBUG: execute_test returned None for test {test_id}!")
            logger.error(f"🚨 DEBUG: This should never happen - execute_test should always return a dict")
        elif not isinstance(result, dict):
            logger.warning(f"⚠️ DEBUG: execute_test returned non-dict type {type(result)} for test {test_id}: {result}")
        else:
            logger.debug(f"✅ DEBUG: execute_test returned valid dict for test {test_id} with keys: {list(result.keys())}")
            # Check if required fields are present
            required_fields = ['test_id', 'execution_time']
            missing_fields = [field for field in required_fields if field not in result]
            if missing_fields:
                logger.warning(f"⚠️ DEBUG: Result missing required fields {missing_fields} for test {test_id}")
        
        # Ensure we always return a valid result for chord collection
        if result is None:
            logger.error(f"🚨 DEBUG: Converting None result to failure dict for test {test_id}")
            result = {
                "test_id": test_id,
                "status": "failed",
                "error": "execute_test returned None - this indicates a bug in execute_test",
                "execution_time": 0
            }
        elif not isinstance(result, dict):
            logger.error(f"🚨 DEBUG: Converting non-dict result to failure dict for test {test_id}")
            result = {
                "test_id": test_id,
                "status": "failed",
                "error": f"execute_test returned non-dict type: {type(result)}",
                "execution_time": 0,
                "original_result": str(result)
            }
        
        # Update test run progress - determine if test was successful
        was_successful = (
            isinstance(result, dict) and 
            result.get("status") != "failed" and 
            result is not None
        )
        
        # Increment the progress counter
        progress_updated = increment_test_run_progress(
            db=db,
            test_run_id=test_run_id,
            test_id=test_id,
            was_successful=was_successful
        )
        
        if progress_updated:
            logger.debug(f"✅ DEBUG: Updated test run progress for test {test_id}, successful: {was_successful}")
        else:
            logger.warning(f"⚠️ DEBUG: Failed to update test run progress for test {test_id}")
        
        logger.info(f"✅ DEBUG: execute_single_test completing successfully for test {test_id}")
        return result

    except Exception as e:
        logger.error(f"🚨 DEBUG: Exception in execute_single_test for test {test_id}: {str(e)}", exc_info=True)
        
        # Log additional context about the exception
        logger.error(f"🚨 DEBUG: Exception type: {type(e).__name__}")
        logger.error(f"🚨 DEBUG: Exception args: {e.args}")
        
        db.rollback()
        
        # Create a failure result to prevent None in chord results
        failure_result = {
            "test_id": test_id,
            "status": "failed",
            "error": str(e),
            "execution_time": 0,
            "exception_type": type(e).__name__
        }
        
        logger.error(f"🚨 DEBUG: Created failure_result for test {test_id}: {failure_result}")
        
        # Update progress for failed test
        try:
            progress_updated = increment_test_run_progress(
                db=db,
                test_run_id=test_run_id,
                test_id=test_id,
                was_successful=False
            )
            if progress_updated:
                logger.debug(f"✅ DEBUG: Updated test run progress for failed test {test_id}")
            else:
                logger.warning(f"⚠️ DEBUG: Failed to update test run progress for failed test {test_id}")
        except Exception as progress_error:
            logger.error(f"🚨 DEBUG: Exception updating progress for failed test {test_id}: {str(progress_error)}")
        
        # Pass explicit organization_id and user_id on retry to ensure context is preserved
        if self.request.retries < self.max_retries:
            logger.warning(f"⚠️ DEBUG: Attempting retry {self.request.retries + 1}/{self.max_retries} for test {test_id}")
            # Use explicit raise with retry=True to preserve context
            try:
                self.retry(
                    exc=e, 
                    kwargs={
                        "test_config_id": test_config_id,
                        "test_run_id": test_run_id,
                        "test_id": test_id,
                        "endpoint_id": endpoint_id,
                        "organization_id": organization_id,
                        "user_id": user_id
                    }
                )
            except self.MaxRetriesExceededError:
                # Return failure result instead of raising exception
                logger.error(f"🚨 DEBUG: Test {test_id} failed after max retries, returning failure result")
                return failure_result
        
        # Return failure result instead of raising exception
        logger.error(f"🚨 DEBUG: Returning failure result for test {test_id} (no retries left)")
        return failure_result 