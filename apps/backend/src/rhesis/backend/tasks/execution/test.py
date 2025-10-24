from rhesis.backend.app import crud
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.utils.llm_utils import get_user_evaluation_model
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.base import SilentTask
from rhesis.backend.tasks.execution.test_execution import execute_test
from rhesis.backend.tasks.utils import increment_test_run_progress
from rhesis.backend.worker import app


@app.task(
    name="rhesis.backend.tasks.execute_single_test",
    base=SilentTask,
    bind=True,
    display_name="Individual Test Execution",
)
# with_tenant_context decorator removed - tenant context now passed directly
def execute_single_test(
    self,
    test_config_id: str,
    test_run_id: str,
    test_id: str,
    endpoint_id: str,
    organization_id: str = None,  # Make this explicit so it's preserved on retries
    user_id: str = None,  # Make this explicit so it's preserved on retries
):
    """
    Execute a single test and return its results.

    This task gets tenant context passed directly and should use
    handle database sessions with the proper tenant context.
    """
    # Access context from task request - task headers take precedence over kwargs
    task = self.request
    request_user_id = getattr(task, "user_id", None)
    request_org_id = getattr(task, "organization_id", None)

    # Use passed parameters if available, otherwise use request context
    # This ensures context is preserved during retries
    user_id = user_id or request_user_id
    organization_id = organization_id or request_org_id

    try:
        # Use tenant-aware database session with explicit organization_id and user_id
        with get_db_with_tenant_variables(organization_id, user_id) as db:
            # Fetch user's evaluation model for metrics
            model = None
            try:
                user = crud.get_user(db, user_id=user_id)
                if user:
                    # Get model settings to log the model name
                    model_settings = user.settings.models.evaluation
                    model_id = model_settings.model_id

                    # Fetch the actual model
                    model = get_user_evaluation_model(db, user)

                    # Log detailed model selection information
                    if isinstance(model, str):
                        logger.info(
                            f"[MODEL_SELECTION] Using default provider '{model}' for test {test_id}"
                        )
                    else:
                        # It's a BaseLLM instance - log detailed info
                        provider = (
                            model.model_name.split("/")[0] if "/" in model.model_name else "unknown"
                        )
                        model_name = (
                            model.model_name.split("/")[1]
                            if "/" in model.model_name
                            else model.model_name
                        )

                        # Try to get the user-friendly name from database
                        if model_id:
                            db_model = crud.get_model(
                                db,
                                model_id=str(model_id),
                                organization_id=str(user.organization_id),
                            )
                            if db_model:
                                logger.info(
                                    f"[MODEL_SELECTION] Using user-configured model for test {test_id}: "
                                    f"name='{db_model.name}', provider={provider}, model={model_name}, id={model_id}"
                                )
                            else:
                                logger.info(
                                    f"[MODEL_SELECTION] Using evaluation model for test {test_id}: "
                                    f"provider={provider}, model={model_name}, id={model_id}"
                                )
                        else:
                            logger.info(
                                f"[MODEL_SELECTION] Using evaluation model for test {test_id}: "
                                f"provider={provider}, model={model_name}"
                            )
                else:
                    logger.warning(
                        f"[MODEL_SELECTION] User {user_id} not found, will use default model"
                    )
            except Exception as e:
                logger.warning(
                    f"[MODEL_SELECTION] Error fetching user model for test {test_id}: {str(e)}, will use default"
                )
                model = None

            # Call the main execution function from the dedicated module
            result = execute_test(
                db=db,
                test_config_id=test_config_id,
                test_run_id=test_run_id,
                test_id=test_id,
                endpoint_id=endpoint_id,
                organization_id=organization_id,
                user_id=user_id,
                model=model,
            )

        # Add detailed debugging about the result
        if result is None:
            logger.error(f"🚨 DEBUG: execute_test returned None for test {test_id}!")
            logger.error(
                "🚨 DEBUG: This should never happen - execute_test should always return a dict"
            )
        elif not isinstance(result, dict):
            logger.warning(
                f"⚠️ DEBUG: execute_test returned non-dict type {type(result)} for test {test_id}: {result}"
            )
        else:
            logger.debug(
                f"✅ DEBUG: execute_test returned valid dict for test {test_id} with keys: {list(result.keys())}"
            )
            # Check if required fields are present
            required_fields = ["test_id", "execution_time"]
            missing_fields = [field for field in required_fields if field not in result]
            if missing_fields:
                logger.warning(
                    f"⚠️ DEBUG: Result missing required fields {missing_fields} for test {test_id}"
                )

        # Ensure we always return a valid result for chord collection
        if result is None:
            logger.error(f"🚨 DEBUG: Converting None result to failure dict for test {test_id}")
            result = {
                "test_id": test_id,
                "status": "failed",
                "error": "execute_test returned None - this indicates a bug in execute_test",
                "execution_time": 0,
            }
        elif not isinstance(result, dict):
            logger.error(f"🚨 DEBUG: Converting non-dict result to failure dict for test {test_id}")
            result = {
                "test_id": test_id,
                "status": "failed",
                "error": f"execute_test returned non-dict type: {type(result)}",
                "execution_time": 0,
                "original_result": str(result),
            }

        # Update test run progress - determine if test was successful
        was_successful = (
            isinstance(result, dict) and result.get("status") != "failed" and result is not None
        )

        # Increment the progress counter
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
            logger.debug(
                f"✅ DEBUG: Updated test run progress for test {test_id}, successful: {was_successful}"
            )
        else:
            logger.warning(f"⚠️ DEBUG: Failed to update test run progress for test {test_id}")

        logger.info(f"✅ DEBUG: execute_single_test completing successfully for test {test_id}")
        return result

    except Exception as e:
        logger.error(
            f"🚨 DEBUG: Exception in execute_single_test for test {test_id}: {str(e)}",
            exc_info=True,
        )

        # Log additional context about the exception
        logger.error(f"🚨 DEBUG: Exception type: {type(e).__name__}")
        logger.error(f"🚨 DEBUG: Exception args: {e.args}")

        # Transaction rollback is handled by the session context manager

        # Create a failure result to prevent None in chord results
        failure_result = {
            "test_id": test_id,
            "status": "failed",
            "error": str(e),
            "execution_time": 0,
            "exception_type": type(e).__name__,
        }

        logger.error(f"🚨 DEBUG: Created failure_result for test {test_id}: {failure_result}")

        # Update progress for failed test
        try:
            with get_db_with_tenant_variables(organization_id, user_id) as db:
                progress_updated = increment_test_run_progress(
                    db=db,
                    test_run_id=test_run_id,
                    test_id=test_id,
                    was_successful=False,
                    organization_id=organization_id,
                    user_id=user_id,
                )
                if progress_updated:
                    logger.debug(f"✅ DEBUG: Updated test run progress for failed test {test_id}")
                else:
                    logger.warning(
                        f"⚠️ DEBUG: Failed to update test run progress for failed test {test_id}"
                    )
        except Exception as progress_error:
            logger.error(
                f"🚨 DEBUG: Exception updating progress for failed test {test_id}: {str(progress_error)}"
            )

        # Pass explicit organization_id and user_id on retry to ensure context is preserved
        if self.request.retries < self.max_retries:
            logger.warning(
                f"⚠️ DEBUG: Attempting retry {self.request.retries + 1}/{self.max_retries} for test {test_id}"
            )
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
                        "user_id": user_id,
                    },
                )
            except self.MaxRetriesExceededError:
                # Return failure result instead of raising exception
                logger.error(
                    f"🚨 DEBUG: Test {test_id} failed after max retries, returning failure result"
                )
                return failure_result

        # Return failure result instead of raising exception
        logger.error(f"🚨 DEBUG: Returning failure result for test {test_id} (no retries left)")
        return failure_result
