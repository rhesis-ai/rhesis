"""
Single-turn test executor.

Handles traditional request-response test execution with single prompt evaluation.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.dependencies import get_endpoint_service
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.tasks.execution.evaluation import evaluate_prompt_response
from rhesis.backend.tasks.execution.executors.base import BaseTestExecutor
from rhesis.backend.tasks.execution.executors.shared import (
    check_existing_result,
    create_test_result_record,
    get_test_and_prompt,
    get_test_metrics,
    prepare_metric_configs,
    process_endpoint_result,
)


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

    def execute(
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
        logger.info(f"[SingleTurnExecutor] Starting test execution for test {test_id}")
        start_time = datetime.utcnow()

        try:
            # Check for existing result to avoid duplicates
            existing_result = check_existing_result(
                db, test_config_id, test_run_id, test_id, organization_id, user_id
            )
            if existing_result:
                logger.info(f"[SingleTurnExecutor] Found existing result for test {test_id}")
                return existing_result

            # Retrieve test data
            test, prompt_content, expected_response = get_test_and_prompt(
                db, test_id, organization_id
            )
            logger.debug(
                f"[SingleTurnExecutor] Retrieved test data - "
                f"prompt length: {len(prompt_content)}"
            )

            # Prepare metrics
            metrics = get_test_metrics(test)
            metric_configs = prepare_metric_configs(metrics, test_id)
            logger.debug(f"[SingleTurnExecutor] Prepared {len(metric_configs)} valid metrics")

            # Execute endpoint
            endpoint_service = get_endpoint_service()
            input_data = {"input": prompt_content}

            result = endpoint_service.invoke_endpoint(
                db=db,
                endpoint_id=endpoint_id,
                input_data=input_data,
                organization_id=organization_id,
            )

            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.debug(
                f"[SingleTurnExecutor] Endpoint execution completed in {execution_time:.2f}ms"
            )

            # Evaluate metrics
            context = result.get("context", []) if result else []

            # Pass user's configured model, db session, and org ID to evaluator
            # This allows metrics to use their own configured models if available
            metrics_evaluator = MetricEvaluator(model=model, db=db, organization_id=organization_id)

            # Log model being used for metrics evaluation
            if model:
                model_info = (
                    model
                    if isinstance(model, str)
                    else f"{type(model).__name__}(model_name={model.model_name})"
                )
                logger.debug(
                    f"[METRICS_EVALUATION] Evaluating test {test_id} with "
                    f"default model: {model_info}"
                )
            else:
                logger.debug(
                    f"[METRICS_EVALUATION] Evaluating test {test_id} with system default model"
                )

            metrics_results = evaluate_prompt_response(
                metrics_evaluator=metrics_evaluator,
                prompt_content=prompt_content,
                expected_response=expected_response,
                context=context,
                result=result,
                metrics=metric_configs,
            )

            # Process result and store
            processed_result = process_endpoint_result(result)

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
            result_summary = {
                "test_id": test_id,
                "execution_time": execution_time,
                "metrics": metrics_results,
            }

            logger.info(
                f"[SingleTurnExecutor] Test execution completed successfully for test {test_id}"
            )
            return result_summary

        except Exception as e:
            logger.error(
                f"[SingleTurnExecutor] Test execution failed for test {test_id}: {str(e)}",
                exc_info=True,
            )
            raise
