from collections import defaultdict
from datetime import datetime
from typing import Dict, List
from uuid import UUID

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.database import SessionLocal, set_tenant
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.base import EmailEnabledTask
from rhesis.backend.tasks.execution.run import update_test_run_status
from rhesis.backend.tasks.enums import RunStatus
from rhesis.backend.worker import app


@app.task(base=EmailEnabledTask, bind=True, max_retries=3, retry_backoff=True, retry_backoff_max=60)
def collect_results(self, results, start_time, test_config_id, test_run_id, test_set_id, total_tests, organization_id=None, user_id=None):
    """
    Collect and aggregate results from test execution.
    
    This task is called as a callback after all individual test execution tasks have completed.
    It updates the test run status and aggregates metrics from all tests.
    
    For Redis chords, the results are automatically collected via chord context.
    """
    logger.info(f"Chord callback triggered for test run {test_run_id}")
    logger.info(f"Processing {len(results) if results else 0} task results")
    
    if not results:
        logger.warning(f"No results provided to callback for test run {test_run_id}")
    
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
        
        logger.info(f"Task completion: {len(successful_results)} successful, {failed_tasks} failed out of {total_tests} total")
        
        if failed_tasks > 0:
            logger.warning(f"{failed_tasks} tasks failed for test run {test_run_id}")

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
            
            # Get real-time progress from test run attributes (updated by individual tests)
            current_attributes = test_run.attributes if test_run.attributes else {}
            real_time_completed = current_attributes.get("completed_tests", 0)
            real_time_failed = current_attributes.get("failed_tests", 0)
            
            # Use real-time counters if available, otherwise fall back to result processing
            actual_completed = real_time_completed if real_time_completed > 0 else len(successful_results)
            actual_failed = real_time_failed if real_time_failed > 0 else failed_tasks
            
            # Log comparison for debugging
            logger.info(f"Progress tracking - Real-time: {real_time_completed} completed, {real_time_failed} failed | "
                       f"Result processing: {len(successful_results)} successful, {failed_tasks} failed")
            
            # Determine status based on failures
            status = RunStatus.COMPLETED.value
            if actual_failed > 0:
                status = RunStatus.PARTIAL.value if actual_failed < total_tests else RunStatus.FAILED.value
            
            # Prepare the complete attributes update including completion data
            completed_at = datetime.utcnow().isoformat()
            updated_attributes = test_run.attributes.copy()  # Copy existing attributes
            updated_attributes.update({
                "completed_at": completed_at,
                "total_tests": total_tests,
                "completed_tests": actual_completed,  # Use real-time counter
                "failed_tests": actual_failed,       # Use real-time counter  
                "failed_tasks": failed_tasks,        # Keep original for compatibility
                "mean_execution_time_ms": mean_execution_time,
                "total_execution_time_ms": total_execution_time_ms,
                "task_state": status,  # Explicitly set the final task_state
                "status": status,      # Also set status for consistency
                "collect_results_called": True,  # Proof that callback was executed
                "final_update": True,  # Mark this as the final update
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
            
            # Send email notification with test execution summary
            try:
                # Get user for email notification
                user = crud.get_user(db, UUID(user_id)) if user_id else None
                if user and user.email and not user.email.endswith('@example.com'):
                    
                    # Calculate execution summary
                    total_execution_time_seconds = int(total_execution_time_ms / 1000)
                    minutes, seconds = divmod(total_execution_time_seconds, 60)
                    execution_time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
                    
                    # Determine overall status for email
                    email_status = "success" if status == RunStatus.COMPLETED.value else "failed"
                    
                    # Create detailed status message
                    if status == RunStatus.COMPLETED.value:
                        status_message = f"All {actual_completed} tests passed successfully"
                        email_status = "success"
                    elif status == RunStatus.PARTIAL.value:
                        status_message = f"{actual_completed} tests passed, {actual_failed} tests failed"
                        email_status = "partial"
                    else:
                        status_message = f"Test execution failed ({actual_failed} of {total_tests} tests failed)"
                        email_status = "failed"
                    
                    # Import email service to use specialized method
                    from rhesis.backend.tasks.email_service import email_service
                    
                    # Send the specialized test execution summary email
                    success = email_service.send_test_execution_summary_email(
                        recipient_email=user.email,
                        recipient_name=user.name,
                        task_name="Test Configuration Execution",
                        task_id=self.request.id,
                        status=email_status,
                        total_tests=total_tests,
                        tests_passed=actual_completed,
                        tests_failed=actual_failed,
                        execution_time=execution_time_str,
                        test_run_id=test_run_id,
                        status_details=status_message,
                        frontend_url=None  # Will use default from environment
                    )
                    
                    if success:
                        logger.info(f"Test execution summary email sent for test run {test_run_id} to {user.email}")
                    else:
                        logger.warning(f"Failed to send test execution summary email for test run {test_run_id} to {user.email}")
                else:
                    logger.debug(f"Skipping email notification - no valid user email found")
                    
            except Exception as e:
                # Don't fail the entire task if email fails
                logger.error(f"Failed to send email notification for test run {test_run_id}: {str(e)}")
        else:
            logger.error(f"Test run {test_run_id} not found in database!")

        return {
            "test_run_id": test_run_id,
            "test_config_id": test_config_id,
            "total_tests": total_tests,
            "completed_tests": actual_completed,  # Use real-time counter
            "failed_tests": actual_failed,       # Use real-time counter
            "failed_tasks": failed_tasks,        # Keep original for compatibility
            "mean_execution_time_ms": mean_execution_time,
            "callback_executed": True,
        }

    except Exception as e:
        logger.error(f"Error in collect_results callback: {str(e)}", exc_info=True)
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
                    "collect_results_error": True,
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
                "status": "failed",
                "callback_executed": False,
            }
        else:
            raise
    finally:
        db.close() 