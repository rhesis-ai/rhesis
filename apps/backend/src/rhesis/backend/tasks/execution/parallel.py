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
    session: Session, test_config: TestConfiguration, test_run: TestRun, tests: List
) -> Dict[str, Any]:
    """Execute test cases in parallel using Celery workers with Redis native chord support."""
    logger.info(f"Starting parallel execution for test run {test_run.id} with {len(tests)} tests")

    # Create tasks for parallel execution
    tasks = []
    for test in tests:
        task = execute_single_test.s(
            test_config_id=str(test_config.id),
            test_run_id=str(test_run.id),
            test_id=str(test.id),
            endpoint_id=str(test_config.endpoint_id),
            organization_id=str(test_config.organization_id)
            if test_config.organization_id
            else None,
            user_id=str(test_config.user_id) if test_config.user_id else None,
        )
        tasks.append(task)

    # Create callback task with correct parameters and context for the decorator-based collect_results
    callback = collect_results.s(
        str(test_run.id),  # test_run_id (after results parameter)
    ).set(
        # Pass context in headers so BaseTask.before_start can pick them up
        headers={
            "organization_id": str(test_config.organization_id)
            if test_config.organization_id
            else None,
            "user_id": str(test_config.user_id) if test_config.user_id else None,
        }
    )

    # Record start time before chord execution
    start_time = datetime.utcnow()

    # Execute the chord
    job = chord(tasks, callback).apply_async()
    logger.info(f"Chord created with ID: {job.id}")

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
