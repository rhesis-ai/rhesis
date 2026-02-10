"""
Main orchestration module for test execution.

This module determines the execution mode and delegates to the appropriate
execution strategy (parallel or sequential).
"""

from typing import Any, Dict

from sqlalchemy.orm import Session

from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.services.test_set import get_test_set
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import ExecutionMode
from rhesis.backend.tasks.execution.modes import get_execution_mode
from rhesis.backend.tasks.execution.parallel import execute_tests_in_parallel
from rhesis.backend.tasks.execution.sequential import execute_tests_sequentially


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

    # Get test set and tests
    test_set = get_test_set(session, str(test_config.test_set_id))
    tests = test_set.tests

    if not tests:
        logger.warning(f"No tests found in test set {test_set.id}")
        return {
            "test_run_id": str(test_run.id),
            "test_configuration_id": str(test_config.id),
            "test_set_id": str(test_config.test_set_id),
            "total_tests": 0,
        }

    # Determine execution mode
    execution_mode = get_execution_mode(test_config)
    logger.info(f"Executing test configuration {test_config.id} in {execution_mode.value} mode")

    # Delegate to the appropriate execution strategy
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
        return execute_tests_in_parallel(
            session,
            test_config,
            test_run,
            tests,
            reference_test_run_id=reference_test_run_id,
            trace_id=trace_id,
        )
