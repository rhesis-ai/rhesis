"""
Main orchestration module for test execution.

This module determines the execution mode and delegates to the appropriate
execution strategy (parallel, batch, or sequential).
"""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.services.test_set import count_test_set_tests, get_test_set
from rhesis.backend.tasks.enums import ExecutionMode
from rhesis.backend.tasks.execution.batch import execute_tests_as_batch
from rhesis.backend.tasks.execution.modes import get_execution_mode
from rhesis.backend.tasks.execution.run import TestExecutionError
from rhesis.backend.tasks.execution.sequential import execute_tests_sequentially

logger = logging.getLogger(__name__)


def execute_test_cases(
    session: Session,
    test_config: TestConfiguration,
    test_run: TestRun,
    reference_test_run_id: str = None,
    trace_id: str = None,
) -> Dict[str, Any]:
    """Execute test cases based on the configured execution mode.

    Args:
        session: Database session
        test_config: Test configuration model
        test_run: Test run model
        reference_test_run_id: Optional previous test run ID for re-scoring
        trace_id: Optional trace ID for trace-based evaluation
    """

    test_set = get_test_set(session, str(test_config.test_set_id))
    if count_test_set_tests(session, test_set.id) == 0:
        raise TestExecutionError(
            "Cannot execute test set with 0 tests. Please add tests before executing."
        )

    tests = test_set.tests

    execution_mode = get_execution_mode(test_config)
    logger.info(f"Executing test configuration {test_config.id} in {execution_mode.value} mode")

    if execution_mode == ExecutionMode.SEQUENTIAL:
        return execute_tests_sequentially(
            session,
            test_config,
            test_run,
            tests,
            reference_test_run_id=reference_test_run_id,
            trace_id=trace_id,
        )
    else:
        return execute_tests_as_batch(
            session,
            test_config,
            test_run,
            tests,
            reference_test_run_id=reference_test_run_id,
            trace_id=trace_id,
        )
