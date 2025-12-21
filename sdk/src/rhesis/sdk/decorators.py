"""Decorators for collaborative testing."""

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Optional

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


def collaborate(
    name: str | None = None,
    request_mapping: dict | None = None,
    response_mapping: dict | None = None,
    span_name: str | None = None,
    **metadata,
) -> Callable:
    """
    Decorator for collaborative testing and observability.

    This decorator enables two features:
    1. TRACING (Always On): Traces all normal executions and sends to backend
    2. TESTING (On-Demand): Enables remote triggering from Rhesis platform

    Args:
        name: Optional function name for registration (defaults to function.__name__)
        span_name: Optional semantic span name (e.g., 'ai.llm.invoke', 'ai.tool.invoke')
            Defaults to 'function.<name>' if not provided.
            This allows power users to specify AI operation types for better observability.
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
        @collaborate()
        def chat(input: str, session_id: str = None):
            # REQUEST: input, session_id auto-detected
            # RESPONSE: output, session_id auto-extracted
            return {"output": "...", "session_id": session_id}

        # Example 2: Manual mapping with custom naming
        @collaborate(
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
        @collaborate(
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
                "before using @collaborate decorator."
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
            # Delegate tracing to connector manager
            if _default_client._connector_manager:
                return _default_client._connector_manager.trace_execution(
                    func_name, func, args, kwargs, span_name
                )
            # Fallback: just execute function without tracing
            return func(*args, **kwargs)

        return wrapper

    return decorator
