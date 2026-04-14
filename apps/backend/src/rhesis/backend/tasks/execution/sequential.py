"""
Sequential execution implementation for test cases.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.tasks.enums import ExecutionMode
from rhesis.backend.tasks.execution.shared import (
    create_execution_result,
    create_failure_result,
    trigger_results_collection,
    update_test_run_start,
)
from rhesis.backend.tasks.execution.test_execution import execute_test

logger = logging.getLogger(__name__)


def execute_tests_sequentially(
    session: Session,
    test_config: TestConfiguration,
    test_run: TestRun,
    tests: List,
    reference_test_run_id: str = None,
    trace_id: str = None,
) -> Dict[str, Any]:
    """Execute test cases sequentially, one after another.

    Args:
        session: Database session
        test_config: Test configuration model
        test_run: Test run model
        tests: List of test models to execute
        reference_test_run_id: Optional previous test run ID for re-scoring
        trace_id: Optional trace ID for trace-based evaluation
    """
    logger.info(f"Starting sequential execution for test run {test_run.id} with {len(tests)} tests")

    start_time = datetime.utcnow()
    results = []

    # Update test run with start information using shared utility
    update_test_run_start(session, test_run, ExecutionMode.SEQUENTIAL, len(tests), start_time)

    # Resolve execution and evaluation models from test_config.attributes
    # overrides or user defaults (same logic as batch prefetch_execution_context).
    execution_model = None
    evaluation_model = None
    try:
        from rhesis.backend.app import crud
        from rhesis.backend.app.constants import DEFAULT_EVALUATION_MODEL, DEFAULT_EXECUTION_MODEL
        from rhesis.backend.app.utils.user_model_utils import (
            get_evaluation_model_with_override,
            get_execution_model_with_override,
        )

        attrs = test_config.attributes or {}
        override_execution_model_id = attrs.get("execution_model_id")
        override_evaluation_model_id = attrs.get("evaluation_model_id")
        seq_user_id = str(test_config.user_id) if test_config.user_id else None

        if seq_user_id:
            user = crud.get_user_by_id(session, seq_user_id)
            if user:
                execution_model = get_execution_model_with_override(
                    session, user, model_id=override_execution_model_id
                )
                evaluation_model = get_evaluation_model_with_override(
                    session, user, model_id=override_evaluation_model_id
                )
            else:
                logger.warning(f"User {seq_user_id} not found, using default models")
                execution_model = DEFAULT_EXECUTION_MODEL
                evaluation_model = DEFAULT_EVALUATION_MODEL
        else:
            execution_model = DEFAULT_EXECUTION_MODEL
            evaluation_model = DEFAULT_EVALUATION_MODEL
    except Exception as e:
        from rhesis.backend.app.constants import DEFAULT_EVALUATION_MODEL, DEFAULT_EXECUTION_MODEL

        logger.warning(f"Failed to resolve execution/evaluation models: {e}")
        if execution_model is None:
            execution_model = DEFAULT_EXECUTION_MODEL
        if evaluation_model is None:
            evaluation_model = DEFAULT_EVALUATION_MODEL

    # Execute tests one by one
    for i, test in enumerate(tests, 1):
        logger.info(f"Executing test {i}/{len(tests)}: {test.id}")

        try:
            import asyncio

            result = asyncio.run(
                execute_test(
                    db=session,
                    test_config_id=str(test_config.id),
                    test_run_id=str(test_run.id),
                    test_id=str(test.id),
                    endpoint_id=str(test_config.endpoint_id),
                    organization_id=str(test_config.organization_id)
                    if test_config.organization_id
                    else None,
                    user_id=str(test_config.user_id) if test_config.user_id else None,
                    execution_model=execution_model,
                    evaluation_model=evaluation_model,
                    reference_test_run_id=reference_test_run_id,
                    trace_id=trace_id,
                )
            )
            results.append(result)

            logger.info(f"Test {i}/{len(tests)} completed successfully")

        except Exception as e:
            logger.error(f"Test {i}/{len(tests)} failed: {str(e)}")
            # Create failure result using shared utility
            failure_result = create_failure_result(str(test.id), e)
            results.append(failure_result)

    end_time = datetime.utcnow()
    execution_time = (end_time - start_time).total_seconds()

    logger.info(
        f"Sequential execution completed for test run {test_run.id} in {execution_time:.2f} seconds"
    )

    # Trigger results collection as a proper Celery task to get the same
    # processing as parallel execution
    try:
        collection_task = trigger_results_collection(test_config, str(test_run.id), results)
        logger.info(f"Results collection task started: {collection_task.id}")
    except Exception as e:
        logger.error(f"Error triggering results collection: {str(e)}")

    # Return standardized result using shared utility
    return create_execution_result(
        test_run,
        test_config,
        len(tests),
        ExecutionMode.SEQUENTIAL,
        execution_time=execution_time,
        completed_at=end_time.isoformat(),
    )
