"""
Test execution entry point and backward compatibility layer.

This module provides the main execute_test() entry point which delegates to
appropriate executors based on test type (Strategy Pattern).

Helper functions are re-exported from executors.shared for backward compatibility
with existing tests and code.
"""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

# Additional backward compatibility imports for functions moved during refactoring
from rhesis.backend.logging.rhesis_logger import logger

# Import factory for executor creation
from rhesis.backend.tasks.execution.executors import create_executor

# Import get_test_and_prompt from data module
from rhesis.backend.tasks.execution.executors.data import get_test_and_prompt

# Import output providers for re-scoring and trace evaluation
from rhesis.backend.tasks.execution.executors.output_providers import (
    TestResultOutput,
    TraceOutput,
)

# ============================================================================
# MAIN EXECUTION FUNCTION (Strategy Pattern Entry Point)
# ============================================================================


async def execute_test(
    db: Session,
    test_config_id: str,
    test_run_id: str,
    test_id: str,
    endpoint_id: str,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    model: Optional[Any] = None,
    reference_test_run_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a test and return its results.

    This function is the main entry point for test execution. It uses the Strategy
    Pattern to delegate to the appropriate executor based on the test's type:
    - Single-Turn tests -> SingleTurnTestExecutor
    - Multi-Turn tests -> MultiTurnTestExecutor
    - Future types -> New executors can be added without modifying this code

    The function maintains backward compatibility with existing code while enabling
    a more modular and extensible architecture.

    Args:
        db: Database session
        test_config_id: UUID string of the test configuration
        test_run_id: UUID string of the test run
        test_id: UUID string of the test
        endpoint_id: UUID string of the endpoint
        organization_id: UUID string of the organization (optional)
        user_id: UUID string of the user (optional)
        model: Optional model override for evaluation
        reference_test_run_id: Optional UUID string of a previous test run
            to re-score. When provided, output is loaded from stored
            TestResults instead of invoking the endpoint.
        trace_id: Optional trace ID for trace-based evaluation. When
            provided, output is loaded from stored Trace records.

    Returns:
        Dictionary with test execution results containing:
        - test_id: The test ID
        - execution_time: Time taken in milliseconds
        - metrics: Dictionary of metric evaluation results

    Raises:
        ValueError: If test or prompt is not found
        Exception: If test execution fails

    Examples:
        >>> # Normal execution
        >>> result = await execute_test(
        ...     db=db, test_config_id="config-uuid",
        ...     test_run_id="run-uuid", test_id="test-uuid",
        ...     endpoint_id="endpoint-uuid",
        ... )
        >>> # Re-scoring from a previous run
        >>> result = await execute_test(
        ...     db=db, ...,
        ...     reference_test_run_id="previous-run-uuid",
        ... )
    """
    logger.info(f"Starting test execution for test {test_id}")

    try:
        # Create output provider based on mode
        output_provider = None
        if reference_test_run_id:
            output_provider = TestResultOutput(reference_test_run_id)
            logger.info(f"Re-scoring test {test_id} from run {reference_test_run_id}")
        elif trace_id:
            output_provider = TraceOutput(trace_id)
            logger.info(f"Evaluating test {test_id} from trace {trace_id}")
        # else: None -> runner uses its default (live execution)

        # Retrieve test to determine type
        test, _, _ = get_test_and_prompt(db, test_id, organization_id)
        logger.debug(f"Retrieved test {test_id}, determining executor...")

        # Create appropriate executor based on test type (Strategy Pattern)
        executor = create_executor(test)

        # Delegate execution to the executor
        result = await executor.execute(
            db=db,
            test_config_id=test_config_id,
            test_run_id=test_run_id,
            test_id=test_id,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
            model=model,
            output_provider=output_provider,
        )

        logger.info(f"Test execution completed successfully for test {test_id}")
        return result

    except Exception as e:
        logger.error(
            f"Test execution failed for test {test_id}: {str(e)}",
            exc_info=True,
        )
        raise


# ============================================================================
# BACKWARD COMPATIBILITY NOTES
# ============================================================================
#
# This module maintains backward compatibility by:
#
# 1. execute_test() function signature remains unchanged
# 2. Helper functions (get_test_and_prompt, get_test_metrics, etc.) are
#    re-exported from executors.shared
# 3. Return value structure remains the same across all executor types
#
# Existing code and tests should continue to work without modifications:
#
#   from rhesis.backend.tasks.execution.test_execution import (
#       execute_test,              # Main entry point
#       get_test_and_prompt,       # Helper functions
#       get_test_metrics,
#       prepare_metric_configs,
#   )
#
# New code can use executors directly for more control:
#
#   from rhesis.backend.tasks.execution.executors import (
#       create_executor,
#       SingleTurnTestExecutor,
#       MultiTurnTestExecutor,
#   )
#
# ============================================================================
