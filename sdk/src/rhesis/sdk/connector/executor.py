"""Test executor for remote function execution."""

import asyncio
import inspect
import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class TestExecutor:
    """Handles execution of remote test requests."""

    def _serialize_result(self, result: Any) -> Any:
        """
        Serialize result, handling Pydantic models automatically.

        Args:
            result: Function output (dict, primitive, or Pydantic model)

        Returns:
            Serialized result (always JSON-compatible)
        """
        # Check if result is a Pydantic model
        if hasattr(result, "model_dump"):
            return result.model_dump()
        # Already serializable (dict, list, str, int, etc.)
        return result

    async def execute(
        self,
        func: Callable,
        function_name: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a function with given inputs.

        Args:
            func: Function to execute
            function_name: Name of the function (for logging)
            inputs: Function input parameters

        Returns:
            Dictionary with execution results:
                - status: "success" or "error"
                - output: Function output (if successful)
                - error: Error message (if failed)
                - duration_ms: Execution duration in milliseconds
        """
        start_time = time.time()

        try:
            # Execute function (sync or async)
            if asyncio.iscoroutinefunction(func):
                result = await func(**inputs)
            else:
                result = func(**inputs)

            # Handle generators (consume and collect output)
            result = await self._consume_generator(result)

            # Serialize Pydantic models to dicts
            result = self._serialize_result(result)

            duration_ms = (time.time() - start_time) * 1000

            return {
                "status": "success",
                "output": result,
                "error": None,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Error executing function {function_name}: {e}")

            return {
                "status": "error",
                "output": None,
                "error": str(e),
                "duration_ms": duration_ms,
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
