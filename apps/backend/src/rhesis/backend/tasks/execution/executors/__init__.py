"""
Test executors using Strategy Pattern.

This module provides different execution strategies for various test types:
- SingleTurnTestExecutor: Traditional request-response tests
- MultiTurnTestExecutor: Agentic multi-turn tests using Penelope

The factory pattern (create_executor) automatically selects the appropriate
executor based on the test's type.

New modular structure:
- data: Data retrieval utilities
- metrics: Metrics processing and evaluation
- results: Result storage and processing
- runners: Core execution logic (shared by executors and in-place service)
- output_providers: Pluggable output acquisition strategies
"""

from rhesis.backend.tasks.execution.executors.base import BaseTestExecutor
from rhesis.backend.tasks.execution.executors.data import (
    get_test_and_prompt,
    get_test_metrics,
)
from rhesis.backend.tasks.execution.executors.factory import create_executor
from rhesis.backend.tasks.execution.executors.metrics import (
    determine_status_from_metrics,
    prepare_metric_configs,
)
from rhesis.backend.tasks.execution.executors.multi_turn import (
    MultiTurnTestExecutor,
)
from rhesis.backend.tasks.execution.executors.output_providers import (
    MultiTurnOutput,
    MultiTurnTraceOutput,
    OutputProvider,
    SingleTurnOutput,
    TestOutput,
    TestResultOutput,
    TraceOutput,
    get_provider_metadata,
)
from rhesis.backend.tasks.execution.executors.results import (
    check_existing_result,
    create_test_result_record,
)
from rhesis.backend.tasks.execution.executors.runners import (
    BaseRunner,
    MultiTurnRunner,
    SingleTurnRunner,
)
from rhesis.backend.tasks.execution.executors.single_turn import (
    SingleTurnTestExecutor,
)

__all__ = [
    # Core executors
    "BaseTestExecutor",
    "SingleTurnTestExecutor",
    "MultiTurnTestExecutor",
    "create_executor",
    # Runners (shared logic)
    "BaseRunner",
    "SingleTurnRunner",
    "MultiTurnRunner",
    # Output providers
    "OutputProvider",
    "TestOutput",
    "SingleTurnOutput",
    "MultiTurnOutput",
    "TestResultOutput",
    "TraceOutput",
    "MultiTurnTraceOutput",
    "get_provider_metadata",
    # Data utilities
    "get_test_and_prompt",
    "get_test_metrics",
    # Metrics utilities
    "prepare_metric_configs",
    "determine_status_from_metrics",
    # Result utilities
    "check_existing_result",
    "create_test_result_record",
]
