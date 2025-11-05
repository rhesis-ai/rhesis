"""
Execution mode configuration utilities.

This module provides helper functions for working with execution modes
and test types in test configurations.
"""

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import ExecutionMode, TestType
from rhesis.backend.tasks.utils import safe_uuid_convert


def get_execution_mode(test_config: TestConfiguration) -> ExecutionMode:
    """
    Get the execution mode from test configuration attributes.
    Defaults to Parallel if not specified.

    Args:
        test_config: TestConfiguration object

    Returns:
        ExecutionMode: The execution mode (Sequential or Parallel)
    """
    if not test_config.attributes:
        return ExecutionMode.PARALLEL

    execution_mode = test_config.attributes.get("execution_mode", ExecutionMode.PARALLEL)

    # Ensure it's a valid ExecutionMode
    if isinstance(execution_mode, str):
        try:
            return ExecutionMode(execution_mode)
        except ValueError:
            logger.warning(
                f"Invalid execution_mode '{execution_mode}' in test config {test_config.id}, defaulting to Parallel"
            )
            return ExecutionMode.PARALLEL

    return execution_mode if isinstance(execution_mode, ExecutionMode) else ExecutionMode.PARALLEL


def set_execution_mode(
    db: Session,
    test_config_id: str,
    execution_mode: ExecutionMode,
    organization_id: str = None,
    user_id: str = None,
) -> bool:
    """
    Set the execution mode for a test configuration.

    Args:
        db: Database session
        test_config_id: Test configuration UUID string
        execution_mode: ExecutionMode enum value

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get test configuration
        test_config_uuid = safe_uuid_convert(test_config_id)
        if not test_config_uuid:
            logger.error(f"Invalid test configuration ID: {test_config_id}")
            return False

        test_config = crud.get_test_configuration(
            db, test_config_uuid, organization_id=organization_id, user_id=user_id
        )
        if not test_config:
            logger.error(f"Test configuration not found: {test_config_id}")
            return False

        # Update attributes
        current_attributes = test_config.attributes.copy() if test_config.attributes else {}
        current_attributes["execution_mode"] = execution_mode.value

        # Update the test configuration
        update_data = {"attributes": current_attributes}
        crud.update_test_configuration(
            db,
            test_config.id,
            crud.schemas.TestConfigurationUpdate(**update_data),
            organization_id=organization_id,
            user_id=user_id,
        )

        logger.info(
            f"Set execution mode to {execution_mode.value} for test config {test_config_id}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to set execution mode: {str(e)}")
        return False


def get_mode_description(execution_mode: ExecutionMode) -> str:
    """
    Get a human-readable description of an execution mode.

    Args:
        execution_mode: ExecutionMode enum value

    Returns:
        str: Description of the execution mode
    """
    descriptions = {
        ExecutionMode.SEQUENTIAL: (
            "Tests are executed one after another in sequence. "
            "This prevents overwhelming endpoints but takes longer to complete."
        ),
        ExecutionMode.PARALLEL: (
            "Tests are executed simultaneously using multiple workers. "
            "This is faster but may overwhelm endpoints with high load."
        ),
    }

    return descriptions.get(execution_mode, "Unknown execution mode")


def get_mode_recommendations() -> dict:
    """
    Get recommendations for when to use each execution mode.

    Returns:
        dict: Recommendations for each execution mode
    """
    return {
        ExecutionMode.SEQUENTIAL: {
            "use_when": [
                "Testing endpoints that can't handle high concurrent load",
                "Tests have dependencies or need to run in a specific order",
                "Debugging test execution issues",
                "Endpoints with rate limiting",
                "Limited endpoint resources",
            ],
            "pros": [
                "Prevents endpoint overload",
                "Easier to debug individual test failures",
                "Predictable resource usage",
                "Better for rate-limited endpoints",
            ],
            "cons": [
                "Slower overall execution time",
                "Less efficient resource utilization",
                "Longer wait times for results",
            ],
        },
        ExecutionMode.PARALLEL: {
            "use_when": [
                "Endpoints can handle concurrent requests",
                "Tests are independent of each other",
                "You need faster test execution",
                "Scalable endpoints without rate limits",
                "High-performance testing scenarios",
            ],
            "pros": [
                "Faster overall execution time",
                "Better resource utilization",
                "Scales with available workers",
                "Efficient for large test suites",
            ],
            "cons": [
                "May overwhelm endpoints",
                "Harder to debug concurrent failures",
                "Requires more system resources",
                "May hit rate limits",
            ],
        },
    }


# ============================================================================
# TEST TYPE UTILITIES
# ============================================================================


def get_test_type(test: Test) -> TestType:
    """
    Get the test type from a test model.
    Defaults to Single-Turn if not specified or if test_type is not found.

    Args:
        test: Test model instance

    Returns:
        TestType: The test type (Single-Turn or Multi-Turn)
    """
    if not test.test_type:
        logger.debug(f"Test {test.id} has no test_type set, defaulting to Single-Turn")
        return TestType.SINGLE_TURN

    # Get the type_value from the TypeLookup relationship
    test_type_value = test.test_type.type_value

    # Try to match against TestType enum values
    try:
        return TestType(test_type_value)
    except ValueError:
        logger.warning(
            f"Test {test.id} has unknown test_type '{test_type_value}', defaulting to Single-Turn"
        )
        return TestType.SINGLE_TURN


def is_multi_turn_test(test: Test) -> bool:
    """
    Check if a test is a multi-turn test.

    Args:
        test: Test model instance

    Returns:
        bool: True if the test is multi-turn, False otherwise
    """
    return get_test_type(test) == TestType.MULTI_TURN


def is_single_turn_test(test: Test) -> bool:
    """
    Check if a test is a single-turn test.

    Args:
        test: Test model instance

    Returns:
        bool: True if the test is single-turn, False otherwise
    """
    return get_test_type(test) == TestType.SINGLE_TURN


def get_test_type_description(test_type: TestType) -> str:
    """
    Get a human-readable description of a test type.

    Args:
        test_type: TestType enum value

    Returns:
        str: Description of the test type
    """
    descriptions = {
        TestType.SINGLE_TURN: (
            "Single-turn test: Traditional request-response test with a single prompt "
            "and expected response. Metrics are evaluated by the worker."
        ),
        TestType.MULTI_TURN: (
            "Multi-turn test: Agentic conversation test using Penelope. The agent "
            "interacts with the endpoint over multiple turns to achieve a goal. "
            "Goal achievement and metrics are evaluated by Penelope."
        ),
    }

    return descriptions.get(test_type, "Unknown test type")
