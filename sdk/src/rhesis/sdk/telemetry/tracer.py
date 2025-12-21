"""Core tracing functionality using OpenTelemetry."""

import inspect
import logging
from collections.abc import Callable, Generator
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Optional

from opentelemetry import trace

from rhesis.sdk.telemetry.provider import get_tracer_provider

logger = logging.getLogger(__name__)


def _get_sdk_version() -> str:
    """Get the SDK version from package metadata."""
    try:
        return version("rhesis-sdk")
    except PackageNotFoundError:
        # Fallback for development/testing environments
        return "dev"


class Tracer:
    """
    Traces function execution using OpenTelemetry.

    This is the primary tracing API. Any part of the SDK can use this
    to trace operations.
    """

    def __init__(
        self,
        api_key: str,
        project_id: str,
        environment: str,
        base_url: str,
    ):
        """
        Initialize tracer with OTEL infrastructure.

        Args:
            api_key: API key for authentication
            project_id: Project identifier
            environment: Environment name
            base_url: Base URL for backend
        """
        self.api_key = api_key
        self.project_id = project_id
        self.environment = environment
        self.base_url = base_url

        # Initialize OTEL provider
        provider = get_tracer_provider(
            service_name="rhesis-sdk",
            api_key=api_key,
            base_url=base_url,
            project_id=project_id,
            environment=environment,
        )

        self.tracer = provider.get_tracer("rhesis.sdk", _get_sdk_version())

    def trace_execution(
        self,
        function_name: str,
        func: Callable,
        args: tuple,
        kwargs: dict,
        span_name: Optional[str] = None,
    ) -> Any:
        """
        Trace function execution with OTEL spans.

        Args:
            function_name: Name of the function
            func: The function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            span_name: Optional custom span name (e.g., 'ai.llm.invoke')
                      Defaults to 'function.<name>' if not provided

        Returns:
            Function result (or wrapped generator)
        """
        # Determine span name
        final_span_name = span_name or f"function.{function_name}"

        # Start OTEL span
        with self.tracer.start_as_current_span(
            name=final_span_name,
            kind=trace.SpanKind.INTERNAL,
        ) as span:
            # Set basic attributes
            span.set_attribute("function.name", function_name)
            span.set_attribute("function.args_count", len(args))
            span.set_attribute("function.kwargs_count", len(kwargs))

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Handle generator functions
                if inspect.isgenerator(result):
                    logger.debug(f"Function {function_name} returned generator")
                    return self._wrap_generator(span, function_name, result)

                # Handle regular functions
                span.set_status(trace.Status(trace.StatusCode.OK))

                # Add result preview (limited size)
                result_str = str(result)[:1000]
                span.set_attribute("function.result_preview", result_str)

                return result

            except Exception as e:
                # Record error
                span.set_status(trace.Status(trace.StatusCode.ERROR, description=str(e)))
                span.record_exception(e)
                raise

    def _wrap_generator(
        self,
        span: trace.Span,
        function_name: str,
        generator: Generator,
    ) -> Generator:
        """
        Wrap a generator to capture output for tracing.

        Args:
            span: Active OTEL span
            function_name: Name of the function
            generator: The generator to wrap

        Yields:
            Items from the original generator
        """
        collected_output = []

        try:
            for item in generator:
                collected_output.append(str(item)[:100])
                yield item

            # Generator completed successfully
            span.set_status(trace.Status(trace.StatusCode.OK))
            span.set_attribute("function.output_chunks", len(collected_output))

        except Exception as e:
            # Generator failed
            span.set_status(trace.Status(trace.StatusCode.ERROR, description=str(e)))
            span.record_exception(e)
            raise
