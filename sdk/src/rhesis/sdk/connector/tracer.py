"""Tracer for function execution observability."""

import inspect
import logging
import threading
import time
from collections.abc import Callable, Generator
from typing import Any

logger = logging.getLogger(__name__)


class Tracer:
    """Handles function execution tracing and telemetry."""

    def __init__(
        self,
        api_key: str,
        project_id: str,
        environment: str,
        base_url: str,
    ):
        """
        Initialize tracer.

        Args:
            api_key: API key for authentication
            project_id: Project identifier
            environment: Environment name
            base_url: Base URL for trace endpoint
        """
        self.api_key = api_key
        self.project_id = project_id
        self.environment = environment
        self.base_url = base_url

    def trace_execution(
        self,
        function_name: str,
        func: Callable,
        args: tuple,
        kwargs: dict,
    ) -> Any:
        """
        Trace function execution and send telemetry to backend.

        This method wraps function execution with tracing logic,
        handling both regular functions and generators.

        Args:
            function_name: Name of the function being traced
            func: The function to execute
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Function result (or wrapped generator)
        """
        start_time = time.time()
        inputs = {"args": args, "kwargs": kwargs}

        try:
            # Execute function
            result = func(*args, **kwargs)

            # Handle generator functions
            if inspect.isgenerator(result):
                logger.debug(f"🔄 {function_name} returned a generator - wrapping for tracing")
                return self._wrap_generator(function_name, result, inputs, start_time)

            # Handle regular functions
            duration_ms = (time.time() - start_time) * 1000
            self._send_trace_async(function_name, inputs, result, duration_ms, "success")
            return result

        except Exception as e:
            # Handle errors
            duration_ms = (time.time() - start_time) * 1000
            self._send_trace_async(function_name, inputs, None, duration_ms, "error", str(e))
            raise

    def _wrap_generator(
        self,
        function_name: str,
        generator: Generator,
        inputs: dict,
        start_time: float,
    ) -> Generator:
        """
        Wrap a generator to capture output for tracing.

        Args:
            function_name: Name of the function
            generator: The generator to wrap
            inputs: Function inputs
            start_time: Execution start time

        Yields:
            Items from the original generator
        """
        collected_output = []

        try:
            for item in generator:
                collected_output.append(str(item))
                yield item

            # Generator completed successfully
            duration_ms = (time.time() - start_time) * 1000
            output = "".join(collected_output)
            self._send_trace_async(function_name, inputs, output, duration_ms, "success")

        except Exception as e:
            # Generator failed
            duration_ms = (time.time() - start_time) * 1000
            self._send_trace_async(function_name, inputs, None, duration_ms, "error", str(e))
            raise

    def _send_trace_async(
        self,
        function_name: str,
        inputs: dict,
        output: Any,
        duration_ms: float,
        status: str,
        error: str | None = None,
    ) -> None:
        """
        Send trace to backend asynchronously (non-blocking).

        Args:
            function_name: Name of the function
            inputs: Function inputs
            output: Function output
            duration_ms: Execution duration in milliseconds
            status: "success" or "error"
            error: Error message if status is "error"
        """
        thread = threading.Thread(
            target=self._send_trace_sync,
            args=(function_name, inputs, output, duration_ms, status, error),
            daemon=True,
        )
        thread.start()

    def _send_trace_sync(
        self,
        function_name: str,
        inputs: dict,
        output: Any,
        duration_ms: float,
        status: str,
        error: str | None = None,
    ) -> None:
        """
        Send trace to backend (called in background thread).

        Args:
            function_name: Name of the function
            inputs: Function inputs
            output: Function output
            duration_ms: Execution duration in milliseconds
            status: "success" or "error"
            error: Error message if status is "error"
        """
        try:
            import requests

            trace_data = {
                "function_name": function_name,
                "inputs": inputs,
                "output": str(output) if output is not None else None,
                "duration_ms": duration_ms,
                "status": status,
                "error": error,
                "timestamp": time.time(),
                "project_id": self.project_id,
                "environment": self.environment,
            }

            # Convert WebSocket URL to HTTP
            if self.base_url.startswith("ws://"):
                http_url = self.base_url.replace("ws://", "http://")
            elif self.base_url.startswith("wss://"):
                http_url = self.base_url.replace("wss://", "https://")
            else:
                http_url = self.base_url

            url = f"{http_url.rstrip('/')}/connector/trace"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            logger.debug(f"📤 Sending trace to {url}")
            logger.debug(
                f"   Function: {function_name}, Status: {status}, Duration: {duration_ms:.2f}ms"
            )

            response = requests.post(url, json=trace_data, headers=headers, timeout=2)
            response.raise_for_status()

            logger.debug(f"✅ Trace sent successfully: {response.status_code}")

        except Exception as e:
            # Log but don't break the application
            logger.warning(f"⚠️ Failed to send trace: {e}")
