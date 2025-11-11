"""
Test executors using Strategy Pattern.

This module provides different execution strategies for various test types:
- SingleTurnTestExecutor: Traditional request-response tests
- MultiTurnTestExecutor: Agentic multi-turn tests using Penelope

The factory pattern (create_executor) automatically selects the appropriate
executor based on the test's type.
"""

from rhesis.backend.tasks.execution.executors.base import BaseTestExecutor
from rhesis.backend.tasks.execution.executors.factory import create_executor
from rhesis.backend.tasks.execution.executors.multi_turn_executor import MultiTurnTestExecutor
from rhesis.backend.tasks.execution.executors.single_turn_executor import SingleTurnTestExecutor

__all__ = [
    "BaseTestExecutor",
    "SingleTurnTestExecutor",
    "MultiTurnTestExecutor",
    "create_executor",
]
