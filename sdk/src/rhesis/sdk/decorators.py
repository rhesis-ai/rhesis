"""Decorators for endpoint registration and observability."""

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

if TYPE_CHECKING:
    from rhesis.sdk.client import Client

# Module-level default client (managed transparently)
_default_client: Optional["Client"] = None


def _register_default_client(client: "Client") -> None:  # pyright: ignore[reportUnusedFunction]
    """
    Internal: Automatically register client (called from Client.__init__).

    Args:
        client: Client instance to register
    """
    global _default_client
    _default_client = client


def observe(
    name: Optional[str] = None,
    span_name: Optional[str] = None,
    **attributes,
) -> Callable:
    """
    Observe function execution with OpenTelemetry tracing.

    Use this for functions that need observability but NOT remote testing.
    For functions that need both, use @endpoint (which includes tracing by default).

    Args:
        name: Display name for the operation (defaults to function name)
        span_name: Semantic span name (e.g., 'ai.llm.invoke', 'function.process')
                  Defaults to 'function.<name>'
        **attributes: Additional span attributes

    Returns:
        Decorated function

    Examples:
        from rhesis.sdk import observe

        # Basic usage
        @observe()
        def process_data(input: str) -> str:
            return llm.generate(input)

        # With semantic span name
        @observe(span_name="ai.llm.invoke")
        def call_llm(prompt: str) -> str:
            return openai.chat.completions.create(...)

        # With custom attributes
        @observe(model="gpt-4", temperature=0.7)
        def generate(prompt: str) -> str:
            return llm.generate(prompt)
    """

    def decorator(func: Callable) -> Callable:
        func_name = name or func.__name__
        final_span_name = span_name or f"function.{func_name}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Validate that telemetry is initialized
            if _default_client is None:
                raise RuntimeError(
                    "RhesisClient not initialized. Create a RhesisClient instance "
                    "before using @observe decorator.\n\n"
                    "Example:\n"
                    "    from rhesis.sdk import RhesisClient\n"
                    "    client = RhesisClient(api_key='...', project_id='...')\n"
                )

            tracer = trace.get_tracer(__name__)

            with tracer.start_as_current_span(
                name=final_span_name,
                kind=SpanKind.INTERNAL,
            ) as span:
                # Set attributes
                span.set_attribute("function.name", func_name)
                for key, value in attributes.items():
                    span.set_attribute(key, value)

                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        return wrapper

    return decorator


def endpoint(
    name: str | None = None,
    request_mapping: dict | None = None,
    response_mapping: dict | None = None,
    span_name: str | None = None,
    observe: bool = True,
    **metadata,
) -> Callable:
    """
    Decorator to register functions as Rhesis endpoints with observability.

    This decorator registers functions as remotely callable Rhesis endpoints.
    It enables two features:
    1. OBSERVABILITY (Default On): Traces all executions with OpenTelemetry
    2. REMOTE TESTING: Enables remote triggering from Rhesis platform

    Args:
        name: Optional function name for registration (defaults to function.__name__)
        span_name: Optional semantic span name (e.g., 'ai.llm.invoke', 'ai.tool.invoke')
            Defaults to 'function.<name>' if not provided.
            This allows power users to specify AI operation types for better observability.
        observe: Enable tracing (default: True). Set to False to disable tracing
            while keeping remote testing capability.
        request_mapping: Manual input mappings (Rhesis standard field → function param)
            Maps incoming API request fields to your function's parameters.
            Standard Rhesis REQUEST fields: input, session_id
            Custom fields: Any additional fields in the request are passed through
            Template syntax: Jinja2 ({{ variable_name }})
            Example: {
                "user_message": "{{ input }}",
                "conv_id": "{{ session_id }}",
                "policy_id": "{{ policy_number }}"  # Custom field
            }
        response_mapping: Manual output mappings (function output → Rhesis standard field)
            Maps your function's return value to Rhesis API response fields.
            Standard Rhesis RESPONSE fields: output, context, metadata, tool_calls
            Path syntax: Jinja2 or JSONPath ($.path.to.field)
            Example: {
                "output": "$.result.text",
                "session_id": "$.conv_id",
                "context": "$.sources",
                "metadata": "$.stats"
            }
        **metadata: Additional metadata about the function

    Returns:
        Decorated function

    Examples:
        # Example 1: Auto-mapping (zero config - recommended)
        @endpoint()
        def chat(input: str, session_id: str = None):
            # REQUEST: input, session_id auto-detected
            # RESPONSE: output, session_id auto-extracted
            return {"output": "...", "session_id": session_id}

        # Example 2: Manual mapping with custom naming
        @endpoint(
            request_mapping={
                "user_query": "{{ input }}",      # Standard field
                "conv_id": "{{ session_id }}",    # Standard field
                "docs": "{{ context }}"           # Standard field
            },
            response_mapping={
                "output": "$.result.text",        # Nested output
                "session_id": "$.conv_id",
                "context": "$.sources"
            }
        )
        def chat(user_query: str, conv_id: str = None, docs: list = None):
            return {"result": {"text": "..."}, "conv_id": conv_id, "sources": [...]}

        # Example 3: Custom fields with manual mapping
        @endpoint(
            request_mapping={
                "question": "{{ input }}",
                "policy_id": "{{ policy_number }}",  # Custom field from request
                "tier": "{{ customer_tier }}"        # Custom field from request
            },
            response_mapping={
                "output": "$.answer",
                "metadata": "$.stats"
            }
        )
        def insurance_query(question: str, policy_id: str, tier: str):
            # Custom fields (policy_number, customer_tier) must be in API request
            return {"answer": "...", "stats": {"premium": tier == "gold"}}

        # Example 4: Opt-out of tracing (rare use case)
        @endpoint(observe=False)
        def simple_function(x: int) -> int:
            # Registered for remote testing but NOT traced
            return x * 2

    Field Separation:
        REQUEST fields (function inputs):
        - input: User query/message (required in API request)
        - session_id: Conversation tracking (optional in API request)
        - custom fields: Any additional fields in the API request

        RESPONSE fields (function outputs):
        - output: Main response text (extracted from function return)
        - context: Retrieved documents/sources
        - metadata: Response metadata/stats
        - tool_calls: Available tools/functions
        - session_id: Can also be in response to preserve conversation ID

    Raises:
        RuntimeError: If RhesisClient not initialized before using decorator
    """

    def decorator(func: Callable) -> Callable:
        if _default_client is None:
            raise RuntimeError(
                "RhesisClient not initialized. Create a RhesisClient instance "
                "before using @endpoint decorator."
            )

        func_name = name or func.__name__

        # Include mappings in metadata sent to backend
        enriched_metadata = metadata.copy()
        if request_mapping:
            enriched_metadata["request_mapping"] = request_mapping
        if response_mapping:
            enriched_metadata["response_mapping"] = response_mapping

        # Lazy connector initialization happens here
        _default_client.register_collaborative_function(func_name, func, enriched_metadata)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Conditionally trace based on observe parameter
            if observe and _default_client._connector_manager:
                return _default_client._connector_manager.trace_execution(
                    func_name, func, args, kwargs, span_name
                )
            # Execute without tracing if observe=False or no connector manager
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Backwards compatibility alias
collaborate = endpoint
