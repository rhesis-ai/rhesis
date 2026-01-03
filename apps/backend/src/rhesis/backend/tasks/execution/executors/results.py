"""Result processing and storage utilities."""

import copy
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import ResultStatus
from rhesis.backend.tasks.execution.response_extractor import extract_response_with_fallback


def serialize_for_json(obj: Any) -> Any:
    """
    Recursively convert to JSON-serializable format.

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


def process_endpoint_result(result: Any) -> Dict:
    """
    Process endpoint result to ensure output field is populated.

    Uses fallback logic from response_extractor.
    Handles both dict results and ErrorResponse Pydantic objects.

    Returns:
        Processed result with output field populated using the fallback hierarchy
    """
    if not result:
        return {}

    # Handle ErrorResponse Pydantic objects by converting to dict
    if hasattr(result, "to_dict"):
        # Use to_dict() method if available (ErrorResponse)
        result_dict = result.to_dict()
    elif hasattr(result, "model_dump"):
        # Use model_dump() for Pydantic v2 models
        result_dict = result.model_dump(exclude_none=True)
    elif hasattr(result, "dict"):
        # Fallback to dict() for Pydantic v1 models
        result_dict = result.dict(exclude_none=True)
    elif isinstance(result, dict):
        # Already a dict
        result_dict = result
    else:
        logger.warning(f"Unexpected result type: {type(result)}, attempting to convert")
        result_dict = dict(result) if result else {}

    # Create a DEEP copy of the result to avoid modifying the original or sharing references
    processed_result = copy.deepcopy(result_dict)

    # Use the existing fallback logic to get the processed output
    processed_output = extract_response_with_fallback(processed_result)

    # Set the output field to the processed response
    processed_result["output"] = processed_output

    return processed_result


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
) -> Optional[UUID]:
    """
    Create and store test result record in database.

    After creating the test result, this function automatically links
    any traces from the test execution to the new test result record.

    Returns:
        UUID of the created test result, or None if creation failed
    """
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

        # Validate that the result has a valid ID
        if not result or not hasattr(result, "id") or result.id is None:
            logger.error(
                f"[TEST_RESULT] Failed to create test result: CRUD operation returned "
                f"invalid result for test_id={test_id}, test_run_id={test_run_id}, "
                f"test_config_id={test_config_id}"
            )
            return None

        result_id = result.id
        logger.info(
            f"[TEST_RESULT] Successfully created test result with ID: {result_id} "
            f"for test_id={test_id}, test_run_id={test_run_id}, "
            f"test_config_id={test_config_id}"
        )

        # Link traces to this test result
        if result_id:
            logger.info(f"[TEST_RESULT] Attempting to link traces to test_result_id={result_id}")
            try:
                from rhesis.backend.app.services.telemetry.linking_service import (
                    TraceLinkingService,
                )

                linking_service = TraceLinkingService(db)
                updated_count = linking_service.link_traces_for_test_result(
                    test_run_id=test_run_id,
                    test_id=test_id,
                    test_configuration_id=test_config_id,
                    test_result_id=str(result_id),
                    organization_id=organization_id,
                )
                logger.info(
                    f"[TEST_RESULT] Trace linking complete: {updated_count} traces "
                    f"linked to test_result_id={result_id}"
                )
            except Exception as trace_error:
                # Don't fail test result creation if trace linking fails
                logger.error(
                    f"[TEST_RESULT] Failed to link traces to test result "
                    f"{result_id}: {trace_error}",
                    exc_info=True,
                )
        else:
            logger.warning(
                "[TEST_RESULT] No result_id returned from create_test_result, "
                "skipping trace linking"
            )

        return result_id

    except Exception as e:
        logger.error(f"[TEST_RESULT] Failed to create test result: {str(e)}", exc_info=True)
        raise
