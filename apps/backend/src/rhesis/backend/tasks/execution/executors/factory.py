"""
Executor factory for routing tests to appropriate executors.

Uses the Strategy Pattern to select the correct executor based on test type.
"""

from rhesis.backend.app.models.test import Test
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.enums import TestType
from rhesis.backend.tasks.execution.executors.base import BaseTestExecutor
from rhesis.backend.tasks.execution.modes import get_test_type


def create_executor(test: Test) -> BaseTestExecutor:
    """
    Factory function to create appropriate executor based on test type.

    This function implements the Strategy Pattern, routing tests to the correct
    executor based on their type. This makes it easy to add new test types
    without modifying existing code (Open/Closed Principle).

    Args:
        test: Test model instance

    Returns:
        Appropriate BaseTestExecutor subclass instance

    Examples:
        >>> test = get_test(db, test_id)
        >>> executor = create_executor(test)
        >>> result = executor.execute(...)

    Future test types can be added here:
        - ImageTestExecutor for vision/multimodal tests
        - AdversarialTestExecutor for security/jailbreak tests
        - SyntheticTestExecutor for generated test cases
        - PerformanceTestExecutor for load/stress testing
    """
    test_type = get_test_type(test)

    logger.debug(f"Creating executor for test {test.id} with type {test_type.value}")

    if test_type == TestType.MULTI_TURN:
        from rhesis.backend.tasks.execution.executors.multi_turn_executor import (
            MultiTurnTestExecutor,
        )

        logger.info(f"Routing test {test.id} to MultiTurnTestExecutor")
        return MultiTurnTestExecutor()
    else:
        # Default to single-turn for backward compatibility
        from rhesis.backend.tasks.execution.executors.single_turn_executor import (
            SingleTurnTestExecutor,
        )

        logger.info(f"Routing test {test.id} to SingleTurnTestExecutor")
        return SingleTurnTestExecutor()
