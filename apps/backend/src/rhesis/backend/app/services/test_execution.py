"""
In-place test execution service.

Provides synchronous test execution without worker infrastructure or database persistence.
Reuses existing executor logic but skips all database operations.
"""

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import ResultStatus
from rhesis.backend.tasks.execution.executors.data import get_test_and_prompt
from rhesis.backend.tasks.execution.executors.metrics import determine_status_from_metrics
from rhesis.backend.tasks.execution.executors.runners import MultiTurnRunner, SingleTurnRunner
from rhesis.backend.tasks.execution.test import get_evaluation_model


async def execute_test_in_place(
    db: Session,
    request_data: Dict[str, Any],
    endpoint_id: str,
    organization_id: str,
    user_id: str,
    evaluate_metrics: bool = True,
) -> Dict[str, Any]:
    """
    Execute a test in-place without worker infrastructure or database persistence.

    Args:
        db: Database session
        request_data: Test data - either test_id or complete test definition
        endpoint_id: Endpoint to execute against
        organization_id: Organization ID
        user_id: User ID
        evaluate_metrics: Whether to evaluate and return test_metrics

    Returns:
        Dictionary matching TestExecuteResponse structure:
        {
            "test_id": str,
            "prompt_id": Optional[str],
            "execution_time": float,
            "test_output": Dict[str, Any],
            "test_metrics": Optional[Dict[str, Any]],
            "status": str,
            "test_configuration": Optional[Dict[str, Any]]
        }

    Raises:
        ValueError: If test or endpoint not found, or invalid configuration
        Exception: If execution fails
    """
    start_time = datetime.utcnow()

    # Get user's default evaluation model
    user_model = get_evaluation_model(db, user_id)
    logger.info(
        f"[InPlaceExecution] Using model for user {user_id}: "
        f"{type(user_model).__name__ if not isinstance(user_model, str) else user_model}"
    )

    # Determine if using existing test or creating temporary one
    test_id = request_data.get("test_id")

    if test_id:
        # Use existing test - fetch from database
        logger.info(f"[InPlaceExecution] Using existing test: {test_id}")
        test = crud.get_test(db, test_id=test_id, organization_id=organization_id, user_id=user_id)
        if not test:
            raise ValueError(f"Test not found: {test_id}")

        # Validate test and get prompt data from database
        test, prompt_content, expected_response = get_test_and_prompt(db, test_id, organization_id)
    else:
        # Create inline test object (looks up behavior for metrics)
        logger.info("[InPlaceExecution] Creating inline test object")
        test = _create_inplace_test(request_data, organization_id, user_id, db)
        test_id = str(test.id)

        # Extract prompt/config data directly from request
        prompt_content = ""
        expected_response = ""
        if hasattr(test, "prompt") and test.prompt:
            prompt_content = test.prompt.get("content", "")
            expected_response = test.prompt.get("expected_response", "")

    # Determine test type
    from rhesis.backend.tasks.enums import TestType
    from rhesis.backend.tasks.execution.modes import get_test_type

    test_type = get_test_type(test)
    is_multi_turn = test_type == TestType.MULTI_TURN

    logger.info(
        f"[InPlaceExecution] Executing {'multi-turn' if is_multi_turn else 'single-turn'} "
        f"test {test_id}"
    )

    # Execute based on test type
    if is_multi_turn:
        result = await _execute_multi_turn_in_place(
            db=db,
            test=test,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
            model=user_model,
            evaluate_metrics=evaluate_metrics,
            start_time=start_time,
        )
    else:
        result = await _execute_single_turn_in_place(
            db=db,
            test=test,
            prompt_content=prompt_content,
            expected_response=expected_response,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
            model=user_model,
            evaluate_metrics=evaluate_metrics,
            start_time=start_time,
        )

    return result


def _create_inplace_test(
    request_data: Dict[str, Any], organization_id: str, user_id: str, db: Session
) -> Any:
    """
    Create an inline test object with behavior lookup for metrics.

    Looks up the behavior by name to retrieve associated metrics,
    enabling metric evaluation for inline tests.
    """
    from uuid import UUID

    # Look up behavior by name to get metrics
    behavior_name = request_data.get("behavior")
    behavior_obj = None
    if behavior_name:
        behavior_obj = (
            db.query(models.Behavior)
            .filter(
                models.Behavior.name == behavior_name,
                models.Behavior.organization_id == UUID(organization_id),
            )
            .first()
        )
        if not behavior_obj:
            logger.warning(
                f"[InPlaceExecution] Behavior '{behavior_name}' not found - "
                f"metrics will not be available"
            )

    # Create a simple namespace object to hold test data
    class InlineTest:
        def __init__(self):
            self.id = uuid4()
            self.organization_id = organization_id
            self.user_id = user_id
            self.prompt = request_data.get("prompt")
            self.prompt_id = uuid4() if self.prompt else None
            self.test_configuration = request_data.get("test_configuration")
            # Set behavior as the actual model object (with metrics relationship)
            self.behavior = behavior_obj
            self.topic = request_data.get("topic")
            self.category = request_data.get("category")
            # For compatibility, set IDs
            self.behavior_id = behavior_obj.id if behavior_obj else None
            self.topic_id = None
            self.category_id = None

            # For get_test_type, we need test_type attribute
            # Auto-detect test type if not explicitly provided
            test_type_str = request_data.get("test_type")
            if not test_type_str:
                # Auto-detect: if test_configuration has a goal, it's Multi-Turn
                if self.test_configuration and isinstance(self.test_configuration, dict):
                    if self.test_configuration.get("goal"):
                        test_type_str = "Multi-Turn"
                    else:
                        test_type_str = "Single-Turn"
                # If prompt is provided, it's Single-Turn
                elif self.prompt:
                    test_type_str = "Single-Turn"

            if test_type_str:

                class TestType:
                    def __init__(self, value):
                        self.type_value = value

                self.test_type = TestType(test_type_str)
            else:
                # None will default to Single-Turn in get_test_type
                self.test_type = None

    return InlineTest()


async def _execute_single_turn_in_place(
    db: Session,
    test: models.Test,
    prompt_content: str,
    expected_response: str,
    endpoint_id: str,
    organization_id: str,
    user_id: str,
    model: Any,
    evaluate_metrics: bool,
    start_time: datetime,
) -> Dict[str, Any]:
    """Execute single-turn test in-place without persistence."""
    test_id = str(test.id)

    # Run core execution (shared with executor)
    runner = SingleTurnRunner()
    execution_time, processed_result, metrics_results = await runner.run(
        db=db,
        test=test,
        endpoint_id=endpoint_id,
        organization_id=organization_id,
        user_id=user_id,
        model=model,  # Use user's default evaluation model
        prompt_content=prompt_content,
        expected_response=expected_response,
        evaluate_metrics=evaluate_metrics,
    )

    # Build API response (no DB persistence)
    test_metrics = None
    status = ResultStatus.ERROR.value

    if evaluate_metrics and metrics_results:
        test_metrics = {
            "execution_time": execution_time,
            "metrics": metrics_results,
        }
        status = determine_status_from_metrics(metrics_results)

    return {
        "test_id": test_id,
        "prompt_id": str(test.prompt_id) if test.prompt_id else None,
        "execution_time": execution_time,
        "test_output": processed_result,
        "test_metrics": test_metrics,
        "status": status,
        "test_configuration": None,
    }


async def _execute_multi_turn_in_place(
    db: Session,
    test: models.Test,
    endpoint_id: str,
    organization_id: str,
    user_id: str,
    model: Any,
    evaluate_metrics: bool,
    start_time: datetime,
) -> Dict[str, Any]:
    """Execute multi-turn test in-place without persistence."""
    test_id = str(test.id)

    # Run core execution (shared with executor)
    runner = MultiTurnRunner()
    execution_time, penelope_trace, metrics_results = await runner.run(
        db=db,
        test=test,
        endpoint_id=endpoint_id,
        organization_id=organization_id,
        user_id=user_id,
        model=model,  # Use user's default evaluation model (also for Penelope)
    )

    # Build API response (no DB persistence)
    test_metrics = None
    status = ResultStatus.ERROR.value

    if evaluate_metrics:
        test_metrics = {
            "execution_time": execution_time,
            "metrics": metrics_results,
        }
        status = determine_status_from_metrics(metrics_results)

    return {
        "test_id": test_id,
        "prompt_id": None,
        "execution_time": execution_time,
        "test_output": penelope_trace,
        "test_metrics": test_metrics,
        "status": status,
        "test_configuration": test.test_configuration,
    }
