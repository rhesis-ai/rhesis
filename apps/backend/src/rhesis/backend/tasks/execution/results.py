from collections import defaultdict
from datetime import datetime
from typing import Dict, List
from uuid import UUID

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.database import SessionLocal, set_tenant
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.execution.run import update_test_run_status
from rhesis.backend.tasks.enums import RunStatus
from rhesis.backend.worker import app


@app.task(bind=True, max_retries=3, retry_backoff=True, retry_backoff_max=60)
def collect_results(self, results, start_time, test_config_id, test_run_id, test_set_id, total_tests, organization_id=None, user_id=None):
    """
    Collect and aggregate results from test execution.
    
    This task is called as a callback after all individual test execution tasks have completed.
    It updates the test run status and aggregates metrics from all tests.
    """
    # Create database session manually
    db = SessionLocal()
    
    try:
        # Set tenant context using the proper database utility function
        set_tenant(db, organization_id=organization_id, user_id=user_id)
        
        # Handle different result formats that might come from chord execution
        processed_results = []
        if results:
            for result in results:
                if result is None:
                    # Handle None results
                    processed_results.append(None)
                elif isinstance(result, list) and len(result) == 2:
                    # Handle [[task_id, result], error] format from failed chord tasks
                    task_result = result[1] if result[1] is not None else None
                    processed_results.append(task_result)
                else:
                    # Handle direct results
                    processed_results.append(result)
        else:
            processed_results = []
        
        # Check for failed tasks and count them
        failed_tasks = sum(1 for result in processed_results if result is None or (isinstance(result, dict) and result.get("status") == "failed"))
        successful_results = [result for result in processed_results if result is not None and (not isinstance(result, dict) or result.get("status") != "failed")]
        
        if failed_tasks > 0:
            logger.warning(f"{failed_tasks} tasks failed out of {total_tests} for test run {test_run_id}")

        # Calculate aggregated metrics from successful results only
        execution_times = []
        for result in successful_results:
            if isinstance(result, dict) and "execution_time" in result:
                execution_times.append(result.get("execution_time", 0))
            elif isinstance(result, dict) and "execution_time_ms" in result:
                execution_times.append(result.get("execution_time_ms", 0))
        
        mean_execution_time = (
            sum(execution_times) / len(execution_times) if execution_times else 0
        )

        # Get the test run using crud
        test_run = crud.get_test_run(db, UUID(test_run_id))
        
        if test_run:
            # Calculate total execution time from start to now
            start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_datetime = datetime.utcnow()
            total_execution_time_ms = (end_datetime - start_datetime).total_seconds() * 1000
            
            # Determine status based on failures
            status = RunStatus.COMPLETED.value
            if failed_tasks > 0:
                status = RunStatus.PARTIAL.value if failed_tasks < total_tests else RunStatus.FAILED.value
            
            # Prepare the complete attributes update including completion data
            completed_at = datetime.utcnow().isoformat()
            updated_attributes = test_run.attributes.copy()  # Copy existing attributes
            updated_attributes.update({
                "completed_at": completed_at,
                "total_tests": total_tests,
                "completed_tests": len(successful_results),
                "failed_tasks": failed_tasks,
                "mean_execution_time_ms": mean_execution_time,
                "total_execution_time_ms": total_execution_time_ms,
                "task_state": status,  # Explicitly set the final task_state
                "status": status,      # Also set status for consistency
                "updated_at": completed_at
            })

            # Create update object with both status and attributes
            from rhesis.backend.app.utils.crud_utils import get_or_create_status
            new_status = get_or_create_status(db, status, "TestRun")
            
            # Use crud.update_test_run directly with all the data at once
            # This ensures a single transaction with proper commit handling
            update_data = {
                "status_id": new_status.id,
                "attributes": updated_attributes
            }
            
            crud.update_test_run(db, test_run.id, crud.schemas.TestRunUpdate(**update_data))
            logger.info(f"Successfully updated test run {test_run_id} with status {status}")
        else:
            logger.error(f"Test run {test_run_id} not found!")

        return {
            "test_run_id": test_run_id,
            "test_config_id": test_config_id,
            "total_tests": total_tests,
            "completed_tests": len(successful_results),
            "failed_tasks": failed_tasks,
            "mean_execution_time_ms": mean_execution_time,
        }

    except Exception as e:
        logger.error(f"Error collecting results: {str(e)}", exc_info=True)
        db.rollback()
        
        # Check if we should retry
        if self.request.retries < self.max_retries:
            logger.warning(f"Retrying collect_results task (attempt {self.request.retries + 1}/{self.max_retries})")
            try:
                # Retry with exponential backoff
                raise self.retry(countdown=min(60 * (2 ** self.request.retries), 300), exc=e)
            except Exception as retry_exc:
                logger.error(f"Failed to retry collect_results: {str(retry_exc)}")
        
        try:
            # Update test run status to failed
            test_run = crud.get_test_run(db, UUID(test_run_id))
            if test_run:
                from rhesis.backend.app.utils.crud_utils import get_or_create_status
                failed_status = get_or_create_status(db, RunStatus.FAILED.value, "TestRun")
                
                # Add error to attributes
                error_attributes = test_run.attributes.copy()
                error_attributes.update({
                    "error": str(e),
                    "task_state": RunStatus.FAILED.value,
                    "updated_at": datetime.utcnow().isoformat()
                })
                
                update_data = {
                    "status_id": failed_status.id,
                    "attributes": error_attributes
                }
                
                crud.update_test_run(db, test_run.id, crud.schemas.TestRunUpdate(**update_data))
        except Exception as update_error:
            logger.error(f"Failed to update test run status: {str(update_error)}")
        
        # Don't re-raise the exception if we've exhausted retries
        # This prevents the chord from getting stuck
        if self.request.retries >= self.max_retries:
            logger.error(f"collect_results task failed permanently after {self.max_retries} retries")
            return {
                "error": str(e),
                "test_run_id": test_run_id,
                "status": "failed"
            }
        else:
            raise
    finally:
        db.close() 