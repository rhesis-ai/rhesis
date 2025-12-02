"""Single-turn test executor."""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.execution.executors.base import BaseTestExecutor
from rhesis.backend.tasks.execution.executors.data import get_test_and_prompt
from rhesis.backend.tasks.execution.executors.results import (
    check_existing_result,
    create_test_result_record,
)
from rhesis.backend.tasks.execution.executors.runners import SingleTurnRunner


class SingleTurnTestExecutor(BaseTestExecutor):
    """
    Executor for single-turn tests (traditional request-response).

    This executor handles the classic test flow:
    1. Send a single prompt to the endpoint
    2. Receive a response
    3. Evaluate the response using configured metrics
    4. Store results

    Metrics are evaluated by the worker using the MetricEvaluator.
    """

    async def execute(
        self,
        db: Session,
        test_config_id: str,
        test_run_id: str,
        test_id: str,
        endpoint_id: str,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute a single-turn test.

        Args:
            db: Database session
            test_config_id: UUID string of the test configuration
            test_run_id: UUID string of the test run
            test_id: UUID string of the test
            endpoint_id: UUID string of the endpoint
            organization_id: UUID string of the organization (optional)
            user_id: UUID string of the user (optional)
            model: Optional model override for metric evaluation

        Returns:
            Dictionary with test execution results:
            {
                "test_id": str,
                "execution_time": float (milliseconds),
                "metrics": Dict[str, Any]
            }

        Raises:
            ValueError: If test or prompt is not found
            Exception: If endpoint invocation or metric evaluation fails
        """
        logger.debug(f"Executing single-turn test: {test_id}")

        try:
            # Check for existing result to avoid duplicates
            existing_result = check_existing_result(
                db, test_config_id, test_run_id, test_id, organization_id, user_id
            )
            if existing_result:
                logger.debug(f"Found existing result for test {test_id}")
                return existing_result

            # Retrieve test data
            test, prompt_content, expected_response = get_test_and_prompt(
                db, test_id, organization_id
            )

            # Run core execution (shared with in-place service)
            runner = SingleTurnRunner()
            execution_time, processed_result, metrics_results = await runner.run(
                db=db,
                test=test,
                endpoint_id=endpoint_id,
                organization_id=organization_id,
                user_id=user_id,
                model=model,
                prompt_content=prompt_content,
                expected_response=expected_response,
                evaluate_metrics=True,
            )

            # Persist to database
            create_test_result_record(
                db=db,
                test=test,
                test_config_id=test_config_id,
                test_run_id=test_run_id,
                test_id=test_id,
                organization_id=organization_id,
                user_id=user_id,
                execution_time=execution_time,
                metrics_results=metrics_results,
                processed_result=processed_result,
            )

            # Return execution summary
            logger.debug(f"Test execution completed: {test_id}")
            return {
                "test_id": test_id,
                "execution_time": execution_time,
                "metrics": metrics_results,
            }

        except Exception as e:
            logger.error(
                f"Test execution failed for {test_id}: {str(e)}",
                exc_info=True,
            )
            raise
