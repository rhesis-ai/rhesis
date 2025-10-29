"""
Core test execution logic for running tests against endpoints and evaluating them.

This module handles the execution of individual tests, including:
- Setting up tenant context
- Retrieving test data and metrics
- Invoking endpoints
- Evaluating responses with metrics
- Processing and storing results
"""

import copy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.dependencies import get_endpoint_service
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.sdk.metrics import MetricConfig
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.tasks.enums import ResultStatus
from rhesis.backend.tasks.execution.evaluation import evaluate_prompt_response
from rhesis.backend.tasks.execution.response_extractor import extract_response_with_fallback

# ============================================================================
# TENANT CONTEXT MANAGEMENT
# ============================================================================


# Tenant context is now passed directly to CRUD operations


# ============================================================================
# DATA RETRIEVAL FUNCTIONS
# ============================================================================


def get_test_and_prompt(
    db: Session, test_id: str, organization_id: Optional[str] = None
) -> Tuple[Test, str, str]:
    """
    Retrieve test and its associated prompt data.

    Returns:
        Tuple of (test, prompt_content, expected_response)

    Raises:
        ValueError: If test or prompt is not found
    """
    # Get the test
    test = crud.get_test(db, UUID(test_id), organization_id=organization_id)
    if not test:
        # Fallback query with organization filter
        test_query = db.query(Test).filter(Test.id == UUID(test_id))
        if organization_id:
            test_query = test_query.filter(Test.organization_id == UUID(organization_id))
        test = test_query.first()

        if not test:
            raise ValueError(f"Test with ID {test_id} not found")

    # Get the prompt
    prompt = test.prompt
    if not prompt:
        raise ValueError(f"Test {test_id} has no associated prompt")

    return test, prompt.content, prompt.expected_response or ""


def get_test_metrics(test: Test) -> List:
    """
    Retrieve and validate metrics for a test from its associated behavior.

    Returns:
        List of valid Metric models
    """
    metrics = []
    behavior = test.behavior

    if behavior and behavior.metrics:
        # Return Metric models directly - evaluator accepts them
        metrics = [metric for metric in behavior.metrics if metric.class_name]

        invalid_count = len(behavior.metrics) - len(metrics)
        if invalid_count > 0:
            logger.warning(
                f"Filtered out {invalid_count} metrics without class_name for test {test.id}"
            )

    # Return empty list if no valid metrics found (no defaults in SDK)
    if not metrics:
        logger.warning(f"No valid metrics found for test {test.id}, returning empty list")
        return []

    return metrics


def check_existing_result(
    db: Session,
    test_config_id: str,
    test_run_id: str,
    test_id: str,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[Dict[str, Any]]:
    """Check if a result already exists for this test configuration."""
    filter_str = f"test_configuration_id eq {test_config_id} and test_run_id eq {test_run_id} and test_id eq {test_id}"
    existing_results = crud.get_test_results(
        db, limit=1, filter=filter_str, organization_id=organization_id, user_id=user_id
    )

    if not existing_results:
        return None

    existing_result = existing_results[0]
    return {
        "test_id": test_id,
        "execution_time": existing_result.test_metrics.get("execution_time"),
        "metrics": existing_result.test_metrics.get("metrics", {}),
    }


# ============================================================================
# METRICS PROCESSING
# ============================================================================


def prepare_metric_configs(metrics: List, test_id: str) -> List:
    """
    Validate and filter metric models.

    The evaluator accepts Metric models directly. This function validates that
    models have required fields and filters out any that are invalid.

    Returns:
        List of valid Metric models
    """
    logger.debug(f"🔍 [DEBUG] prepare_metric_configs received {len(metrics)} metrics")

    # Validate that each metric has required fields
    valid_metrics = []
    invalid_count = 0

    for i, metric in enumerate(metrics):
        # All metrics should be Metric model instances
        if not hasattr(metric, "class_name"):
            logger.warning(f"Metric {i} has unexpected type: {type(metric)}")
            invalid_count += 1
            continue

        if not metric.class_name:
            invalid_count += 1
            logger.warning(f"Skipped metric {i} for test {test_id}: missing class_name")
            continue

        valid_metrics.append(metric)

    if invalid_count > 0:
        logger.warning(f"Skipped {invalid_count} invalid metrics for test {test_id}")

    if not valid_metrics:
        logger.warning(
            f"No valid metrics found for test {test_id}, proceeding without metric evaluation"
        )

    return valid_metrics


# ============================================================================
# RESPONSE PROCESSING
# ============================================================================


def process_endpoint_result(result: Dict) -> Dict:
    """
    Process endpoint result to ensure output field is populated using fallback logic.

    Returns:
        Processed result with output field populated using the fallback hierarchy
    """
    if not result:
        return {}

    # Create a DEEP copy of the result to avoid modifying the original or sharing references
    processed_result = copy.deepcopy(result)

    # Use the existing fallback logic to get the processed output
    processed_output = extract_response_with_fallback(processed_result)

    # Set the output field to the processed response
    processed_result["output"] = processed_output

    return processed_result


# ============================================================================
# RESULT STORAGE
# ============================================================================


def create_test_result_record(
    db: Session,
    test: Test,
    test_config_id: str,
    test_run_id: str,
    test_id: str,
    organization_id: Optional[str],
    user_id: Optional[str],
    execution_time: float,
    metrics_results: Dict,
    processed_result: Dict,
) -> None:
    """Create and store the test result record in the database."""
    # Determine status based on metrics evaluation
    if not metrics_results or len(metrics_results) == 0:
        # No metrics to evaluate - mark as ERROR
        status_value = ResultStatus.ERROR.value
    else:
        # Check if all metrics passed
        all_metrics_passed = all(
            metric_data.get("is_successful", False)
            for metric_data in metrics_results.values()
            if isinstance(metric_data, dict)
        )
        status_value = ResultStatus.PASS.value if all_metrics_passed else ResultStatus.FAIL.value

    test_result_status = get_or_create_status(
        db, status_value, "TestResult", organization_id=organization_id
    )

    test_result_data = {
        "test_configuration_id": UUID(test_config_id),
        "test_run_id": UUID(test_run_id),
        "test_id": UUID(test_id),
        "prompt_id": test.prompt_id,
        "status_id": test_result_status.id,
        "user_id": UUID(user_id) if user_id else None,
        "organization_id": UUID(organization_id) if organization_id else None,
        "test_metrics": {"execution_time": execution_time, "metrics": metrics_results},
        "test_output": processed_result,
    }

    try:
        result = crud.create_test_result(
            db,
            schemas.TestResultCreate(**test_result_data),
            organization_id=organization_id,
            user_id=user_id,
        )
        logger.debug(
            f"Successfully created test result with ID: {result.id if hasattr(result, 'id') else 'UNKNOWN'}"
        )
    except Exception as e:
        logger.error(f"Failed to create test result: {str(e)}")
        raise


# ============================================================================
# MAIN EXECUTION FUNCTION
# ============================================================================


def execute_test(
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
    Execute a single test and return its results.

    This function orchestrates the entire test execution process:
    1. Set up tenant context
    2. Check for existing results
    3. Retrieve test data
    4. Invoke the endpoint
    5. Evaluate metrics
    6. Process and store results

    Args:
        db: Database session
        test_config_id: UUID string of the test configuration
        test_run_id: UUID string of the test run
        test_id: UUID string of the test
        endpoint_id: UUID string of the endpoint
        organization_id: UUID string of the organization (optional)
        user_id: UUID string of the user (optional)

    Returns:
        Dictionary with test execution results containing:
        - test_id: The test ID
        - execution_time: Time taken in milliseconds
        - metrics: Dictionary of metric evaluation results

    Raises:
        ValueError: If test or prompt is not found
        Exception: If endpoint invocation or metric evaluation fails
    """
    logger.info(f"Starting test execution for test {test_id}")
    start_time = datetime.utcnow()

    try:
        # Tenant context should be passed directly to CRUD operations by the calling task

        # Check for existing result to avoid duplicates
        existing_result = check_existing_result(
            db, test_config_id, test_run_id, test_id, organization_id, user_id
        )
        if existing_result:
            logger.info(f"Found existing result for test {test_id}")
            return existing_result

        # Retrieve test data
        test, prompt_content, expected_response = get_test_and_prompt(db, test_id, organization_id)
        logger.debug(f"Retrieved test data - prompt length: {len(prompt_content)}")

        # Prepare metrics
        metrics = get_test_metrics(test)
        metric_configs = prepare_metric_configs(metrics, test_id)
        logger.debug(f"Prepared {len(metric_configs)} valid metrics")

        # Execute endpoint
        endpoint_service = get_endpoint_service()
        input_data = {"input": prompt_content}

        result = endpoint_service.invoke_endpoint(
            db=db, endpoint_id=endpoint_id, input_data=input_data, organization_id=organization_id
        )

        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.debug(f"Endpoint execution completed in {execution_time:.2f}ms")

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
                f"[METRICS_EVALUATION] Evaluating test {test_id} with default model: {model_info}"
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

        logger.info(f"Test execution completed successfully for test {test_id}")
        return result_summary

    except Exception as e:
        logger.error(f"Test execution failed for test {test_id}: {str(e)}", exc_info=True)
        raise
