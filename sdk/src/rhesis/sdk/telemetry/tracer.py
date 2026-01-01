"""Core tracing functionality using OpenTelemetry."""

import inspect
import logging
from collections.abc import Callable, Generator
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Optional

from opentelemetry import trace

from rhesis.sdk.telemetry.constants import TestExecutionContext as TestContextConstants
from rhesis.sdk.telemetry.context import get_test_execution_context
from rhesis.sdk.telemetry.provider import get_tracer_provider
from rhesis.sdk.telemetry.schemas import TestExecutionContext

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

    def _set_test_context_attributes(self, span: trace.Span, context: TestExecutionContext) -> None:
        """
        Set test execution context as span attributes.

        Uses OpenTelemetry semantic conventions with rhesis.test.* namespace.
        All UUID values are converted to strings for span attributes.

        Args:
            span: OpenTelemetry span to annotate
            context: Test execution context with UUID strings
        """
        attrs = TestContextConstants.SpanAttributes
        fields = TestContextConstants.Fields

        span.set_attribute(attrs.TEST_RUN_ID, context.get(fields.TEST_RUN_ID))
        span.set_attribute(attrs.TEST_ID, context.get(fields.TEST_ID))
        span.set_attribute(attrs.TEST_CONFIGURATION_ID, context.get(fields.TEST_CONFIGURATION_ID))

        # test_result_id may be None during execution
        result_id = context.get(fields.TEST_RESULT_ID)
        if result_id:
            span.set_attribute(attrs.TEST_RESULT_ID, result_id)

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
        # Read test execution context from context variable (set by executor)
        # NO LONGER extracted from kwargs - it's not there anymore
        test_context = get_test_execution_context()

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

            # Inject test execution context as span attributes if present
            if test_context:
                self._set_test_context_attributes(span, test_context)
                logger.debug(
                    f"Injected test context into span: "
                    f"run={test_context.get(TestContextConstants.Fields.TEST_RUN_ID)}"
                )

            try:
                # Execute function (kwargs no longer has _rhesis_test_context)
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
