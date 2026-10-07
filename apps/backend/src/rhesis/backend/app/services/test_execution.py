"""
In-place test execution service.

Provides synchronous test execution without worker infrastructure or database persistence.
Reuses existing executor logic but skips all database operations.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

import anyio
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import TestResultStatus
from rhesis.backend.app.crud import test as test_crud
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services.run_models import (
    RunModelNeeds,
    build_models,
    metric_backends,
    model_needs,
)
from rhesis.backend.app.services.usage import dispatch_accrual
from rhesis.backend.jobs.execution.executors.data import get_test_and_prompt, get_test_metrics
from rhesis.backend.jobs.execution.executors.metrics import determine_status_from_metrics
from rhesis.backend.jobs.execution.executors.runners import MultiTurnRunner, SingleTurnRunner

logger = logging.getLogger(__name__)


async def execute_test_in_place(
    db: Session,
    request_data: Dict[str, Any],
    endpoint_id: str,
    organization_id: str,
    user_id: str,
    evaluate_metrics: bool = True,
    current_user: Optional[models.User] = None,
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
        current_user: The caller. When given, a model the test uses that cannot
            be built is refused instead of falling back to the default.

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
        ModelNotConfiguredError: If a model the test uses cannot be built
        Exception: If execution fails

    Note:
        The prefetch below runs off the event loop, but the runners this hands
        ``db`` to (``jobs/execution/executors/runners.py``) still query inside
        their own awaits -- metric lookup, endpoint routing, metric evaluation.
        Until those move off the loop too, ``POST /tests/execute`` stays in
        ``tests/backend/test_no_sync_db_on_loop.py``'s allowlist.
    """
    start_time = datetime.now(timezone.utc)

    # The test lookup and model resolution are the only database work that
    # happens before the first await, so they go to a worker thread in one hop.
    (
        evaluation_model,
        execution_model,
        test,
        test_id,
        prompt_content,
        expected_response,
    ) = await anyio.to_thread.run_sync(
        _prepare_execution,
        db,
        request_data,
        organization_id,
        user_id,
        evaluate_metrics,
        current_user,
    )

    # Determine test type
    from rhesis.backend.app.constants import TestType
    from rhesis.backend.jobs.execution.modes import get_test_type

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
            execution_model=execution_model,
            evaluation_model=evaluation_model,
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
            evaluation_model=evaluation_model,
            evaluate_metrics=evaluate_metrics,
            start_time=start_time,
        )

    # Same unit and timing as a batch run: one test executed, counted once it finishes.
    dispatch_accrual(organization_id, QuotaResource.TEST_EXECUTIONS, 1)
    return result


def _log_resolved_models(user_id: str, evaluation_model: Any, execution_model: Any) -> None:
    """Name the models a run picked, for support when a result looks wrong."""
    for purpose, model in (("evaluation", evaluation_model), ("execution", execution_model)):
        if model is None:
            name = "not needed"
        else:
            name = model if isinstance(model, str) else type(model).__name__
        logger.info(f"[InPlaceExecution] Using {purpose} model for user {user_id}: {name}")


def _load_test_for_execution(
    db: Session, request_data: Dict[str, Any], organization_id: str, user_id: str
) -> Tuple[Any, str, str, str]:
    """Resolve the test to run, existing or inline. Returns (test, id, prompt, expected)."""
    test_id: Optional[str] = request_data.get("test_id")

    if test_id:
        # Use existing test - fetch from database
        logger.info(f"[InPlaceExecution] Using existing test: {test_id}")
        test = test_crud.get_test(
            db, test_id=test_id, organization_id=organization_id, user_id=user_id
        )
        if not test:
            raise ValueError(f"Test not found: {test_id}")

        # Validate test and get prompt data from database
        test, prompt_content, expected_response = get_test_and_prompt(db, test_id, organization_id)
        return test, test_id, prompt_content, expected_response

    # Create inline test object (looks up requirement for metrics)
    logger.info("[InPlaceExecution] Creating inline test object")
    test = _create_inplace_test(request_data, organization_id, user_id, db)

    # Extract prompt/config data directly from request
    prompt_content = ""
    expected_response = ""
    if hasattr(test, "prompt") and test.prompt:
        prompt_content = test.prompt.get("content", "")
        expected_response = test.prompt.get("expected_response", "")
    return test, str(test.id), prompt_content, expected_response


def _model_needs(
    db: Session, test: Any, organization_id: str, user_id: str, evaluate_metrics: bool
) -> RunModelNeeds:
    """Which models this one test uses. Same rule as a full run."""
    from rhesis.backend.app.constants import TestType
    from rhesis.backend.jobs.execution.modes import get_test_type

    if get_test_type(test) == TestType.MULTI_TURN:
        return model_needs([], has_multi_turn=True)
    if not evaluate_metrics:
        return model_needs([], has_multi_turn=False)
    metrics = get_test_metrics(test, db, organization_id, user_id)
    return model_needs(metric_backends(db, metrics), has_multi_turn=False)


def _prepare_execution(
    db: Session,
    request_data: Dict[str, Any],
    organization_id: str,
    user_id: str,
    evaluate_metrics: bool = True,
    current_user: Optional[models.User] = None,
) -> Tuple[Any, Any, Any, str, str, str]:
    """Load the test and build the models it uses. Runs in a worker thread.

    Returns (evaluation_model, execution_model, test, test_id, prompt, expected).
    A model the test does not use comes back as ``None``.

    Everything here is psycopg work reached from an ``async def`` handler, so
    it must not run on the event loop. The runner called afterwards still takes
    the same session -- see the note in ``execute_test_in_place``.
    """
    test, test_id, prompt_content, expected_response = _load_test_for_execution(
        db, request_data, organization_id, user_id
    )

    needs = _model_needs(db, test, organization_id, user_id, evaluate_metrics)
    # With the User, the org's own broken model is an error. With only an id it
    # falls back to the deployment default (see resolve_model).
    run_models = build_models(db, current_user or user_id, needs)
    _log_resolved_models(user_id, run_models.evaluation, run_models.execution)

    return (
        run_models.evaluation,
        run_models.execution,
        test,
        test_id,
        prompt_content,
        expected_response,
    )


def _create_inplace_test(
    request_data: Dict[str, Any], organization_id: str, user_id: str, db: Session
) -> Any:
    """
    Create an inline test object with requirement lookup for metrics.

    Looks up the requirement by name to retrieve associated metrics,
    enabling metric evaluation for inline tests.
    """
    from uuid import UUID

    # Look up requirement by name to get metrics
    requirement_name = request_data.get("requirement")
    requirement_obj = None
    if requirement_name:
        requirement_obj = (
            db.query(models.Requirement)
            .filter(
                models.Requirement.name == requirement_name,
                models.Requirement.organization_id == UUID(organization_id),
            )
            .first()
        )
        if not requirement_obj:
            logger.warning(
                f"[InPlaceExecution] Requirement '{requirement_name}' not found - "
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
            # Set requirement as the actual model object (with metrics relationship)
            self.requirement = requirement_obj
            self.topic = request_data.get("topic")
            self.category = request_data.get("category")
            tp = request_data.get("test_parameters")
            self.test_parameters = tp if isinstance(tp, dict) else {}
            # For compatibility, set IDs
            self.requirement_id = requirement_obj.id if requirement_obj else None
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
    evaluation_model: Any,
    evaluate_metrics: bool,
    start_time: datetime,
) -> Dict[str, Any]:
    """Execute single-turn test in-place without persistence."""
    test_id = str(test.id)

    runner = SingleTurnRunner()
    execution_time, processed_result, metrics_results = await runner.run(
        db=db,
        test=test,
        endpoint_id=endpoint_id,
        organization_id=organization_id,
        user_id=user_id,
        model=evaluation_model,
        prompt_content=prompt_content,
        expected_response=expected_response,
        evaluate_metrics=evaluate_metrics,
    )

    # Build API response (no DB persistence)
    test_metrics = None
    status = TestResultStatus.ERROR.value

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
    execution_model: Any,
    evaluation_model: Any,
    evaluate_metrics: bool,
    start_time: datetime,
) -> Dict[str, Any]:
    """Execute multi-turn test in-place without persistence."""
    test_id = str(test.id)

    runner = MultiTurnRunner()
    execution_time, penelope_trace, metrics_results = await runner.run(
        db=db,
        test=test,
        endpoint_id=endpoint_id,
        organization_id=organization_id,
        user_id=user_id,
        execution_model=execution_model,
        evaluation_model=evaluation_model,
    )

    # Build API response (no DB persistence)
    test_metrics = None
    status = TestResultStatus.ERROR.value

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
