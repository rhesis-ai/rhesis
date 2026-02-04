"""Test executor for remote function execution."""

import asyncio
import contextvars
import inspect
import logging
import time
from collections.abc import Callable
from functools import partial
from typing import Any

from rhesis.sdk.connector.schemas import TestStatus
from rhesis.sdk.connector.serializer import TypeSerializer
from rhesis.sdk.telemetry.constants import TestExecutionContext as TestContextConstants
from rhesis.sdk.telemetry.context import (
    get_root_trace_id,
    set_root_trace_id,
    set_test_execution_context,
)
from rhesis.sdk.telemetry.tracer import pop_result_trace_id

logger = logging.getLogger(__name__)


class TestExecutor:
    """Handles execution of remote test requests with automatic type serialization."""

    def __init__(self, serializers: dict | None = None):
        """
        Initialize the executor.

        Args:
            serializers: Optional global custom serializers for all functions.
                Format: {Type: {"dump": callable, "load": callable}}
        """
        self._global_serializers = serializers

    def _get_serializer(self, function_serializers: dict | None = None) -> TypeSerializer:
        """
        Get a TypeSerializer instance with merged custom serializers.

        Args:
            function_serializers: Function-specific serializers (take precedence)

        Returns:
            TypeSerializer instance
        """
        # Merge global and function-specific serializers
        merged = {}
        if self._global_serializers:
            merged.update(self._global_serializers)
        if function_serializers:
            merged.update(function_serializers)

        return TypeSerializer(custom=merged if merged else None)

    def _prepare_inputs(
        self,
        func: Callable,
        inputs: dict[str, Any],
        serializer: TypeSerializer,
    ) -> dict[str, Any]:
        """
        Prepare inputs by converting dicts to typed objects based on type hints.

        All values flow through the serializer, which decides whether to
        construct typed objects based on the parameter's type annotation.

        Args:
            func: Function to prepare inputs for
            inputs: Raw input dictionary
            serializer: TypeSerializer instance to use

        Returns:
            Dictionary with prepared inputs (typed objects where applicable)
        """
        sig = inspect.signature(func)
        prepared = {}

        for name, param in sig.parameters.items():
            if name not in inputs:
                continue

            value = inputs[name]
            # Let the serializer handle everything uniformly
            prepared[name] = serializer.load(value, param.annotation)

        return prepared

    def _serialize_result(self, result: Any, serializer: TypeSerializer) -> Any:
        """
        Serialize result using the TypeSerializer.

        Handles Pydantic models, dataclasses, and other complex types automatically.

        Args:
            result: Function output (any type)
            serializer: TypeSerializer instance to use

        Returns:
            Serialized result (JSON-compatible)
        """
        return serializer.dump(result)

    async def execute(
        self,
        func: Callable,
        function_name: str,
        inputs: dict[str, Any],
        serializers: dict | None = None,
    ) -> dict[str, Any]:
        """
        Execute a function with given inputs.

        Args:
            func: Function to execute
            function_name: Name of the function (for logging)
            inputs: Function input parameters
            serializers: Optional function-specific custom serializers.
                Format: {Type: {"dump": callable, "load": callable}}

        Returns:
            Dictionary with execution results:
                - status: "success" or "error"
                - output: Function output (if successful)
                - error: Error message (if failed)
                - duration_ms: Execution duration in milliseconds
        """
        start_time = time.time()

        # Get serializer for this execution (merges global and function-specific)
        serializer = self._get_serializer(serializers)

        try:
            # Extract test execution context (internal parameter, not for user function)
            # Store in context variable so tracer can access it
            test_context = inputs.pop(TestContextConstants.CONTEXT_KEY, None)
            if test_context:
                logger.debug(
                    f"Test context for {function_name}: "
                    f"run={test_context.get(TestContextConstants.Fields.TEST_RUN_ID)}"
                )
                set_test_execution_context(test_context)

            try:
                # Prepare inputs: convert dicts to typed objects based on type hints
                prepared_inputs = self._prepare_inputs(func, inputs, serializer)

                # Execute function (sync or async)
                if asyncio.iscoroutinefunction(func):
                    result = await func(**prepared_inputs)
                else:
                    # Run sync functions in thread pool to avoid blocking the event loop
                    # This is critical for long-running functions (e.g., LLM calls) so the
                    # WebSocket can continue responding to pings during execution
                    loop = asyncio.get_running_loop()
                    # Copy context to the thread so contextvars (like test_execution_context)
                    # are available in the function and its nested calls (e.g., tracer)
                    ctx = contextvars.copy_context()
                    result = await loop.run_in_executor(
                        None, partial(ctx.run, func, **prepared_inputs)
                    )

                # Handle generators (consume and collect output)
                result = await self._consume_generator(result)

                # Get trace_id BEFORE serialization (which creates a new object)
                # For sync functions in thread pools, context vars don't propagate back,
                # so check for trace_id stored in thread-safe dict by tracer
                trace_id = get_root_trace_id()
                if trace_id is None and result is not None:
                    trace_id = pop_result_trace_id(result)

                # Serialize result to JSON-compatible format
                result = self._serialize_result(result, serializer)

                duration_ms = (time.time() - start_time) * 1000

                return {
                    "status": TestStatus.SUCCESS,
                    "output": result,
                    "error": None,
                    "duration_ms": duration_ms,
                    "trace_id": trace_id,
                }

            finally:
                # Clear context after execution
                set_test_execution_context(None)
                set_root_trace_id(None)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Error executing function {function_name}: {e}")
            # Clear context on error too
            set_test_execution_context(None)
            set_root_trace_id(None)

            return {
                "status": TestStatus.ERROR,
                "output": None,
                "error": str(e),
                "duration_ms": duration_ms,
                "trace_id": None,
            }

    async def _consume_generator(self, result: Any) -> Any:
        """
        Consume generator if result is a generator.

        Args:
            result: Function result (potentially a generator)

        Returns:
            Original result if not a generator, joined string if generator
        """
        # Check if result is a generator and consume it
        if inspect.isgenerator(result) or inspect.isasyncgen(result):
            chunks = []
            if inspect.isasyncgen(result):
                async for chunk in result:
                    chunks.append(str(chunk))
            else:
                for chunk in result:
                    chunks.append(str(chunk))
            return "".join(chunks)

        return result
