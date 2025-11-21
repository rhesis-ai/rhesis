"""
Shared utilities for test executors.

This module contains helper functions used by multiple test executors.
These functions are re-exported from test_execution.py for backward compatibility.
"""

import copy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import ResultStatus
from rhesis.backend.tasks.execution.constants import MetricScope
from rhesis.backend.tasks.execution.response_extractor import extract_response_with_fallback

# ============================================================================
# SERIALIZATION UTILITIES
# ============================================================================


def serialize_for_json(obj: Any) -> Any:
    """
    Recursively convert an object to JSON-serializable format.

    Handles datetime objects by converting them to ISO format strings.
    Recursively processes dicts, lists, and other nested structures.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable version of the object

    Example:
        >>> data = {"timestamp": datetime.now(), "nested": {"date": datetime.now()}}
        >>> serialized = serialize_for_json(data)
        >>> # All datetime objects are now ISO strings
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    elif hasattr(obj, "__dict__"):
        # Handle Pydantic models and other objects with __dict__
        return serialize_for_json(obj.__dict__)
    else:
        return obj


# ============================================================================
# DATA RETRIEVAL FUNCTIONS
# ============================================================================


def get_test_and_prompt(
    db: Session, test_id: str, organization_id: Optional[str] = None
) -> Tuple[Test, str, str]:
    """
    Retrieve test and its associated prompt data.

    For single-turn tests, validates that a prompt exists.
    For multi-turn tests, validates that test_configuration has a goal defined.

    Returns:
        Tuple of (test, prompt_content, expected_response)
        For multi-turn tests, prompt_content is empty string and expected_response is empty

    Raises:
        ValueError: If test is not found or validation fails
    """
    # Import here to avoid circular dependency
    from rhesis.backend.tasks.enums import TestType
    from rhesis.backend.tasks.execution.modes import get_test_type

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

    # Determine test type
    test_type = get_test_type(test)

    # Validate based on test type
    if test_type == TestType.MULTI_TURN:
        # Multi-turn tests don't have prompts - they have test_configuration with goal
        test_config = test.test_configuration or {}
        goal = test_config.get("goal")

        if not goal:
            raise ValueError(
                f"Multi-turn test {test_id} has no goal defined in test_configuration. "
                "Multi-turn tests require a 'goal' field in test_configuration."
            )

        # Return empty strings for prompt fields (not used in multi-turn)
        return test, "", ""
    else:
        # Single-turn tests require a prompt
        prompt = test.prompt
        if not prompt:
            raise ValueError(
                f"Single-turn test {test_id} has no associated prompt. "
                "Single-turn tests require a prompt."
            )

        return test, prompt.content, prompt.expected_response or ""


def get_test_metrics(
    test: Test, db: Session, organization_id: Optional[str] = None, user_id: Optional[str] = None
) -> List:
    """
    Retrieve and validate metrics for a test from its associated behavior.

    Args:
        test: Test model instance
        db: Database session (needed for RLS context)
        organization_id: Organization ID for RLS policies
        user_id: User ID for RLS policies

    Returns:
        List of valid Metric models
    """
    metrics = []
    behavior = test.behavior

    # CRITICAL: Set RLS session variables before accessing relationships
    # Without this, the behavior.metrics query will fail or return empty due to RLS policies
    from rhesis.backend.app.database import set_session_variables

    if organization_id or user_id:
        try:
            set_session_variables(db, organization_id or "", user_id or "")
        except Exception as e:
            logger.error(f"Failed to set RLS session variables: {e}")

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
    filter_str = (
        f"test_configuration_id eq {test_config_id} and "
        f"test_run_id eq {test_run_id} and test_id eq {test_id}"
    )
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


def filter_metrics_by_scope(metrics: List, scope: MetricScope, test_id: str) -> List:
    """
    Filter metrics by scope (Single-Turn or Multi-Turn).

    Only includes metrics that explicitly have the requested scope in their metric_scope array.
    Metrics without a metric_scope field are excluded.

    Args:
        metrics: List of Metric models
        scope: MetricScope enum value (MetricScope.SINGLE_TURN or MetricScope.MULTI_TURN)
        test_id: Test ID for logging

    Returns:
        List of metrics that support the specified scope
    """
    if not scope:
        return metrics

    filtered_metrics = []
    filtered_out_count = 0
    no_scope_count = 0

    # Get the string value from the enum for comparison with DB values
    scope_value = scope.value

    logger.debug(f"Filtering metrics for test {test_id} with scope: {scope_value}")

    for metric in metrics:
        # Check if metric has metric_scope attribute (stored as array in DB)
        metric_scope = getattr(metric, "metric_scope", None)

        logger.debug(
            f"Checking metric '{metric.name}' (class: {metric.class_name}): "
            f"metric_scope={metric_scope}"
        )

        # Strict filtering: only include metrics with explicit scope
        if not metric_scope or (isinstance(metric_scope, list) and len(metric_scope) == 0):
            # Exclude metrics without scope definition
            no_scope_count += 1
            filtered_out_count += 1
            logger.warning(
                f"Excluded metric '{metric.name}' (class: {metric.class_name}) "
                f"for test {test_id}: metric_scope is not defined. "
                f"Please update the database to set metric_scope for this metric."
            )
            continue

        # metric_scope must be a list/array in the database
        if isinstance(metric_scope, list):
            # Check if the desired scope is in the metric's supported scopes
            if scope_value in metric_scope:
                filtered_metrics.append(metric)
                logger.debug(
                    f"Including metric '{metric.name}': scope {scope_value} found in {metric_scope}"
                )
            else:
                filtered_out_count += 1
                logger.debug(
                    f"Excluded metric '{metric.name}' (class: {metric.class_name}) "
                    f"for test {test_id}: requires scope {metric_scope}, "
                    f"test requires {scope_value}"
                )
        else:
            # Invalid metric_scope type - exclude it
            filtered_out_count += 1
            logger.warning(
                f"Excluded metric '{metric.name}' (class: {metric.class_name}) "
                f"for test {test_id}: metric_scope has invalid type {type(metric_scope)}. "
                f"Expected list/array."
            )

    if no_scope_count > 0:
        logger.warning(
            f"Excluded {no_scope_count} metrics without metric_scope for test {test_id}. "
            f"Please update the database to set metric_scope for all metrics."
        )

    if filtered_out_count > 0:
        logger.info(
            f"Filtered out {filtered_out_count} metrics for test {test_id} "
            f"(test scope: {scope_value})"
        )

    logger.info(
        f"Scope filtering complete for test {test_id}: "
        f"{len(filtered_metrics)}/{len(metrics)} metrics included for scope {scope_value}"
    )

    return filtered_metrics


def prepare_metric_configs(
    metrics: List, test_id: str, scope: Optional[MetricScope] = None
) -> List:
    """
    Validate and filter metric models.

    The evaluator accepts Metric models directly. This function validates that
    models have required fields and filters out any that are invalid or don't
    match the specified scope.

    Args:
        metrics: List of Metric models
        test_id: Test ID for logging
        scope: Optional MetricScope enum to filter by

    Returns:
        List of valid Metric models that match the scope
    """

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

    # Filter by scope if specified
    if scope:
        valid_metrics = filter_metrics_by_scope(valid_metrics, scope, test_id)

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
        result_id = result.id if hasattr(result, "id") else "UNKNOWN"
        logger.debug(f"Successfully created test result with ID: {result_id}")
    except Exception as e:
        logger.error(f"Failed to create test result: {str(e)}")
        raise
