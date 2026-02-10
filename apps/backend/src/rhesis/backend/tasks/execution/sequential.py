"""
Sequential execution implementation for test cases.
"""

from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import ExecutionMode
from rhesis.backend.tasks.execution.shared import (
    create_execution_result,
    create_failure_result,
    store_test_result,
    trigger_results_collection,
    update_test_run_start,
)
from rhesis.backend.tasks.execution.test_execution import execute_test


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

    # Execute tests one by one
    for i, test in enumerate(tests, 1):
        logger.info(f"Executing test {i}/{len(tests)}: {test.id}")

        try:
            # Execute the test asynchronously
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
                    reference_test_run_id=reference_test_run_id,
                    trace_id=trace_id,
                )
            )
            results.append(result)

            # Store the test result in the database (updates test run progress)
            store_test_result(
                session,
                str(test_run.id),
                str(test.id),
                result,
                organization_id=str(test_config.organization_id)
                if test_config.organization_id
                else None,
                user_id=str(test_config.user_id) if test_config.user_id else None,
            )

            logger.info(f"Test {i}/{len(tests)} completed successfully")

        except Exception as e:
            logger.error(f"Test {i}/{len(tests)} failed: {str(e)}")
            # Create failure result using shared utility
            failure_result = create_failure_result(str(test.id), e)
            results.append(failure_result)

            # Store the failure result in the database
            store_test_result(
                session,
                str(test_run.id),
                str(test.id),
                failure_result,
                organization_id=str(test_config.organization_id)
                if test_config.organization_id
                else None,
                user_id=str(test_config.user_id) if test_config.user_id else None,
            )

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
