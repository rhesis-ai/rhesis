"""
Parallel execution implementation for test cases using Celery chord.
"""

from datetime import datetime
from typing import Any, Dict, List

from celery import chord
from sqlalchemy.orm import Session

from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import ExecutionMode
from rhesis.backend.tasks.execution.results import collect_results
from rhesis.backend.tasks.execution.shared import create_execution_result, update_test_run_start
from rhesis.backend.tasks.execution.test import execute_single_test


def execute_tests_in_parallel(
    session: Session,
    test_config: TestConfiguration,
    test_run: TestRun,
    tests: List,
    reference_test_run_id: str = None,
    trace_id: str = None,
) -> Dict[str, Any]:
    """Execute test cases in parallel using Celery workers with Redis native chord support.

    Args:
        session: Database session
        test_config: Test configuration model
        test_run: Test run model
        tests: List of test models to execute
        reference_test_run_id: Optional previous test run ID for re-scoring
        trace_id: Optional trace ID for trace-based evaluation
    """
    logger.info(f"Starting parallel execution for test run {test_run.id} with {len(tests)} tests")

    # Create tasks for parallel execution
    tasks = []
    for test in tests:
        task_kwargs = {
            "test_config_id": str(test_config.id),
            "test_run_id": str(test_run.id),
            "test_id": str(test.id),
            "endpoint_id": str(test_config.endpoint_id),
            "organization_id": str(test_config.organization_id)
            if test_config.organization_id
            else None,
            "user_id": str(test_config.user_id) if test_config.user_id else None,
        }
        # Only include optional params if they have values
        if reference_test_run_id:
            task_kwargs["reference_test_run_id"] = reference_test_run_id
        if trace_id:
            task_kwargs["trace_id"] = trace_id

        task = execute_single_test.s(**task_kwargs)
        tasks.append(task)

    # Create callback task with correct parameters and context for collect_results
    # CRITICAL: For chord callbacks, Celery automatically passes results as first parameter
    # test_run_id must be passed via headers, not as a parameter
    callback = collect_results.s().set(
        # Pass ALL context in headers so BaseTask.before_start can pick them up
        headers={
            "organization_id": str(test_config.organization_id)
            if test_config.organization_id
            else None,
            "user_id": str(test_config.user_id) if test_config.user_id else None,
            "test_run_id": str(test_run.id),  # Pass test_run_id in headers
        }
    )

    # Record start time before chord execution
    start_time = datetime.utcnow()

    # Execute the chord
    job = chord(tasks, callback).apply_async()
    logger.info(f"Chord created with ID: {job.id} for {len(tasks)} tasks")

    # Update test run with chord information using shared utility
    update_test_run_start(
        session,
        test_run,
        ExecutionMode.PARALLEL,
        len(tasks),
        start_time,
        chord_id=job.id,
        chord_parent_id=job.parent.id if job.parent else None,
    )

    # Return standardized result using shared utility
    return create_execution_result(
        test_run,
        test_config,
        len(tasks),
        ExecutionMode.PARALLEL,
        chord_id=job.id,
        chord_parent_id=job.parent.id if job.parent else None,
    )
