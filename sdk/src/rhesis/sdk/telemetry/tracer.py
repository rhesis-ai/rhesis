"""Core tracing functionality using OpenTelemetry."""

import inspect
import logging
from collections.abc import Callable, Generator
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Optional

from opentelemetry import trace

from rhesis.sdk.telemetry.attributes import AIAttributes
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

    def _serialize_arg_for_trace(self, arg: Any, max_length: int = 200) -> Any:
        """
        Intelligently serialize an argument for tracing.

        Extracts useful information from objects automatically without
        requiring users to implement __repr__. This provides good UX by
        making traces informative without requiring any setup.

        Args:
            arg: The argument to serialize
            max_length: Maximum length for string representations

        Returns:
            A JSON-serializable representation of the argument
        """
        # Handle primitives directly
        if isinstance(arg, (str, int, float, bool, type(None))):
            return arg

        # Handle collections recursively (but limit depth)
        if isinstance(arg, (list, tuple)):
            # Limit collection size to prevent huge payloads
            items = arg[:10] if len(arg) > 10 else arg
            serialized = [self._serialize_arg_for_trace(item, max_length) for item in items]
            if len(arg) > 10:
                serialized.append(f"... ({len(arg) - 10} more items)")
            return serialized

        if isinstance(arg, dict):
            # Limit dict size to prevent huge payloads
            items = list(arg.items())[:10]
            serialized = {k: self._serialize_arg_for_trace(v, max_length) for k, v in items}
            if len(arg) > 10:
                serialized["..."] = f"({len(arg) - 10} more items)"
            return serialized

        # For objects, try multiple strategies
        try:
            obj_repr = repr(arg)

            # If object has custom __repr__ (not default), use it
            # Default repr looks like: <module.ClassName object at 0x...>
            if not (obj_repr.startswith("<") and " object at 0x" in obj_repr):
                # Looks like a custom repr - use it
                return obj_repr[:max_length] if len(obj_repr) > max_length else obj_repr

            # Otherwise, extract useful info automatically
            result = {
                "_class": type(arg).__qualname__,
            }

            # Try to extract a few useful public attributes
            try:
                # Get public attributes (not starting with _)
                public_attrs = {}
                for k, v in vars(arg).items():
                    if not k.startswith("_"):
                        # Only include simple types to keep payload small
                        if isinstance(v, (str, int, float, bool, type(None))):
                            public_attrs[k] = v
                        elif isinstance(v, (list, tuple, dict)):
                            # Include abbreviated form of collections
                            if len(str(v)) < 100:
                                public_attrs[k] = v
                            else:
                                public_attrs[k] = f"<{type(v).__name__} with {len(v)} items>"

                if public_attrs:
                    result["_attributes"] = public_attrs
            except (TypeError, AttributeError):
                # Object might not have __dict__ (e.g., slots, builtins)
                pass

            return result

        except Exception:
            # If all else fails, return a safe fallback
            return f"<{type(arg).__qualname__}>"

    def _capture_function_inputs(
        self, span: trace.Span, args: tuple, kwargs: dict, max_length: int = 2000
    ) -> None:
        """
        Capture function inputs as span attributes with intelligent serialization.

        Automatically extracts useful information from objects (including self)
        without requiring users to implement __repr__. This follows industry
        standards (keeping self in traces) while providing great UX.

        Follows semantic layer conventions:
        - function.args: JSON-serialized positional arguments (including self)
        - function.kwargs: JSON-serialized keyword arguments

        Args:
            span: OpenTelemetry span
            args: Positional arguments (including self if instance method)
            kwargs: Keyword arguments
            max_length: Max chars per attribute (default 2000)
        """
        import json

        try:
            # Intelligently serialize args
            if args:
                serialized_args = [self._serialize_arg_for_trace(arg) for arg in args]
                args_str = json.dumps(serialized_args)
                if len(args_str) > max_length:
                    args_str = args_str[:max_length] + "...[truncated]"
                span.set_attribute(AIAttributes.FUNCTION_ARGS, args_str)

            # Serialize kwargs (exclude internal Rhesis fields)
            if kwargs:
                # Filter out internal fields like _rhesis_*
                filtered_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_rhesis")}
                if filtered_kwargs:
                    serialized_kwargs = {
                        k: self._serialize_arg_for_trace(v) for k, v in filtered_kwargs.items()
                    }
                    kwargs_str = json.dumps(serialized_kwargs)
                    if len(kwargs_str) > max_length:
                        kwargs_str = kwargs_str[:max_length] + "...[truncated]"
                    span.set_attribute(AIAttributes.FUNCTION_KWARGS, kwargs_str)

        except Exception as e:
            logger.warning(f"Failed to capture function inputs: {e}")
            # Don't fail tracing if serialization fails

    def trace_execution(
        self,
        function_name: str,
        func: Callable,
        args: tuple,
        kwargs: dict,
        span_name: Optional[str] = None,
        extra_attributes: Optional[dict] = None,
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
            extra_attributes: Optional dictionary of additional span attributes

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

            # Capture function inputs as attributes
            self._capture_function_inputs(span, args, kwargs)

            # Set extra attributes if provided (for @observe decorator)
            if extra_attributes:
                for key, value in extra_attributes.items():
                    span.set_attribute(key, value)

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

                # Add result as structured attribute (with truncation for large results)
                # Use smart serialization for consistency with inputs
                import json

                serialized_result = self._serialize_arg_for_trace(result)
                result_str = (
                    json.dumps(serialized_result)
                    if not isinstance(serialized_result, str)
                    else serialized_result
                )
                if len(result_str) <= 2000:
                    # Store full result if it fits
                    span.set_attribute(AIAttributes.FUNCTION_RESULT, result_str)
                # Always store preview (first 1000 chars)
                span.set_attribute(AIAttributes.FUNCTION_RESULT_PREVIEW, result_str[:1000])

                return result

            except Exception as e:
                # Record error
                span.set_status(trace.Status(trace.StatusCode.ERROR, description=str(e)))
                span.record_exception(e)
                raise

    async def trace_execution_async(
        self,
        function_name: str,
        func: Callable,
        args: tuple,
        kwargs: dict,
        span_name: Optional[str] = None,
        extra_attributes: Optional[dict] = None,
    ) -> Any:
        """
        Trace async function execution with OTEL spans.

        Args:
            function_name: Name of the function
            func: The async function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            span_name: Optional custom span name (e.g., 'ai.llm.invoke')
                      Defaults to 'function.<name>' if not provided
            extra_attributes: Optional dictionary of additional span attributes

        Returns:
            Function result
        """
        # Read test execution context from context variable
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

            # Capture function inputs as attributes
            self._capture_function_inputs(span, args, kwargs)

            # Set extra attributes if provided (for @observe decorator)
            if extra_attributes:
                for key, value in extra_attributes.items():
                    span.set_attribute(key, value)

            # Inject test execution context as span attributes if present
            if test_context:
                self._set_test_context_attributes(span, test_context)
                logger.debug(
                    f"Injected test context into span: "
                    f"run={test_context.get(TestContextConstants.Fields.TEST_RUN_ID)}"
                )

            try:
                # Execute async function
                result = await func(*args, **kwargs)

                # Handle result
                span.set_status(trace.Status(trace.StatusCode.OK))

                # Add result as structured attribute (with truncation for large results)
                # Use smart serialization for consistency with inputs
                import json

                serialized_result = self._serialize_arg_for_trace(result)
                result_str = (
                    json.dumps(serialized_result)
                    if not isinstance(serialized_result, str)
                    else serialized_result
                )
                if len(result_str) <= 2000:
                    # Store full result if it fits
                    span.set_attribute(AIAttributes.FUNCTION_RESULT, result_str)
                # Always store preview (first 1000 chars)
                span.set_attribute(AIAttributes.FUNCTION_RESULT_PREVIEW, result_str[:1000])

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

        Ensures span context remains active during generator consumption
        so nested @observe() decorated methods create child spans, not new traces.

        Args:
            span: Active OTEL span
            function_name: Name of the function
            generator: The generator to wrap

        Yields:
            Items from the original generator
        """
        from opentelemetry import context

        collected_output = []

        # Attach span context so it remains active during generator consumption
        # This ensures nested @observe() calls see this span as parent
        # Using trace.set_span_in_context() is the correct OpenTelemetry API
        token = context.attach(trace.set_span_in_context(span))

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

        finally:
            # Detach context after generator is fully consumed
            context.detach(token)
