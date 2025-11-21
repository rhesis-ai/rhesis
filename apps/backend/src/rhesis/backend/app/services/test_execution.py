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
from rhesis.backend.app.dependencies import get_endpoint_service
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.metrics.evaluator import MetricEvaluator
from rhesis.backend.tasks.enums import ResultStatus
from rhesis.backend.tasks.execution.constants import MetricScope
from rhesis.backend.tasks.execution.evaluation import evaluate_prompt_response
from rhesis.backend.tasks.execution.executors.shared import (
    get_test_and_prompt,
    get_test_metrics,
    prepare_metric_configs,
    process_endpoint_result,
)
from rhesis.backend.tasks.execution.penelope_target import BackendEndpointTarget


def execute_test_in_place(
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
        result = _execute_multi_turn_in_place(
            db=db,
            test=test,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
            evaluate_metrics=evaluate_metrics,
            start_time=start_time,
        )
    else:
        result = _execute_single_turn_in_place(
            db=db,
            test=test,
            prompt_content=prompt_content,
            expected_response=expected_response,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
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


def _execute_single_turn_in_place(
    db: Session,
    test: models.Test,
    prompt_content: str,
    expected_response: str,
    endpoint_id: str,
    organization_id: str,
    user_id: str,
    evaluate_metrics: bool,
    start_time: datetime,
) -> Dict[str, Any]:
    """
    Execute a single-turn test in-place without persistence.

    Adapted from SingleTurnTestExecutor but skips database operations.
    """
    test_id = str(test.id)

    # Prepare metrics if evaluation is requested
    metric_configs = []
    if evaluate_metrics:
        metrics = get_test_metrics(test, db, organization_id, user_id)
        metric_configs = prepare_metric_configs(metrics, test_id, scope=MetricScope.SINGLE_TURN)
        logger.debug(f"[InPlaceExecution] Prepared {len(metric_configs)} valid Single-Turn metrics")

    # Execute endpoint
    endpoint_service = get_endpoint_service()
    input_data = {"input": prompt_content}

    logger.debug(f"[InPlaceExecution] Invoking endpoint {endpoint_id}")
    result = endpoint_service.invoke_endpoint(
        db=db,
        endpoint_id=endpoint_id,
        input_data=input_data,
        organization_id=organization_id,
    )

    # Calculate execution time
    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
    logger.debug(f"[InPlaceExecution] Endpoint execution completed in {execution_time:.2f}ms")

    # Process result
    processed_result = process_endpoint_result(result)

    # Evaluate metrics if requested
    test_metrics = None
    status = ResultStatus.ERROR.value  # Default when no metrics

    if evaluate_metrics and metric_configs:
        logger.debug(f"[InPlaceExecution] Evaluating {len(metric_configs)} metrics")
        context = result.get("context", []) if result else []

        metrics_evaluator = MetricEvaluator(db=db, organization_id=organization_id)
        metrics_results = evaluate_prompt_response(
            metrics_evaluator=metrics_evaluator,
            prompt_content=prompt_content,
            expected_response=expected_response,
            context=context,
            result=result,
            metrics=metric_configs,
        )

        # Build test_metrics structure matching TestResult schema
        test_metrics = {
            "execution_time": execution_time,
            "metrics": metrics_results,
        }

        # Determine status based on metrics
        status = _determine_status_from_metrics(metrics_results)

    # Build response matching TestExecuteResponse schema
    response = {
        "test_id": test_id,
        "prompt_id": str(test.prompt_id) if test.prompt_id else None,
        "execution_time": execution_time,
        "test_output": processed_result,
        "test_metrics": test_metrics,
        "status": status,
        "test_configuration": None,
    }

    logger.info(f"[InPlaceExecution] Single-turn test execution completed for test {test_id}")
    return response


def _execute_multi_turn_in_place(
    db: Session,
    test: models.Test,
    endpoint_id: str,
    organization_id: str,
    user_id: str,
    evaluate_metrics: bool,
    start_time: datetime,
) -> Dict[str, Any]:
    """
    Execute a multi-turn test in-place without persistence.

    Adapted from MultiTurnTestExecutor but skips database operations.
    """
    test_id = str(test.id)

    # Extract multi-turn configuration
    test_config = test.test_configuration or {}
    goal = test_config["goal"]  # Required field
    instructions = test_config.get("instructions")
    scenario = test_config.get("scenario")
    restrictions = test_config.get("restrictions")
    context = test_config.get("context")
    max_turns = test_config.get("max_turns", 10)

    logger.debug(
        f"[InPlaceExecution] Multi-turn config - goal: {goal[:50]}..., max_turns: {max_turns}"
    )

    # Initialize Penelope agent
    from rhesis.penelope import PenelopeAgent

    agent = PenelopeAgent()
    logger.debug("[InPlaceExecution] Initialized Penelope agent")

    # Create backend-specific target
    target = BackendEndpointTarget(
        db=db,
        endpoint_id=endpoint_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    logger.debug(f"[InPlaceExecution] Created BackendEndpointTarget for endpoint {endpoint_id}")

    # Execute test with Penelope
    logger.info("[InPlaceExecution] Executing Penelope test...")
    penelope_result = agent.execute_test(
        target=target,
        goal=goal,
        instructions=instructions,
        scenario=scenario,
        restrictions=restrictions,
        context=context,
        max_turns=max_turns,
    )

    # Calculate execution time
    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
    logger.debug(
        f"[InPlaceExecution] Penelope execution completed in {execution_time:.2f}ms "
        f"({penelope_result.turns_used} turns)"
    )

    # Convert Penelope result to dict
    penelope_trace = penelope_result.model_dump(mode="json")

    # Extract metrics
    metrics_results = penelope_trace.get("metrics", {})

    # Build test_metrics structure if evaluation is requested
    test_metrics = None
    status = ResultStatus.ERROR.value  # Default when no metrics

    if evaluate_metrics:
        test_metrics = {
            "execution_time": execution_time,
            "metrics": metrics_results,
        }
        status = _determine_status_from_metrics(metrics_results)

    # Build response matching TestExecuteResponse schema
    response = {
        "test_id": test_id,
        "prompt_id": None,  # Multi-turn tests don't have prompts
        "execution_time": execution_time,
        "test_output": penelope_trace,  # Complete Penelope trace
        "test_metrics": test_metrics,
        "status": status,
        "test_configuration": test_config,
    }

    logger.info(f"[InPlaceExecution] Multi-turn test execution completed for test {test_id}")
    return response


def _determine_status_from_metrics(metrics: Dict[str, Any]) -> str:
    """
    Determine test status based on metric results.

    Args:
        metrics: Dictionary of metric results

    Returns:
        Status string: "Pass", "Fail", or "Error"
    """
    if not metrics or not isinstance(metrics, dict):
        return ResultStatus.ERROR.value

    # Check if all metrics passed
    all_passed = True
    has_metrics = False

    for metric_name, metric_result in metrics.items():
        if isinstance(metric_result, dict):
            has_metrics = True
            is_successful = metric_result.get("is_successful", False)
            if not is_successful:
                all_passed = False
                break

    if not has_metrics:
        return ResultStatus.ERROR.value

    return ResultStatus.PASS.value if all_passed else ResultStatus.FAIL.value
