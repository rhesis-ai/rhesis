"""Decorators for collaborative testing."""

from collections.abc import Callable
from functools import wraps
from typing import Optional

# Module-level default client (managed transparently)
_default_client: Optional["Client"] = None  # noqa: F821


def _register_default_client(client: "Client") -> None:  # noqa: F821
    """
    Internal: Automatically register client (called from Client.__init__).

    Args:
        client: Client instance to register
    """
    global _default_client
    _default_client = client


def collaborate(
    name: str | None = None,
    request_template: dict | None = None,
    response_mappings: dict | None = None,
    **metadata,
) -> Callable:
    """
    Decorator for collaborative testing and observability.

    This decorator enables two features:
    1. TRACING (Always On): Traces all normal executions and sends to backend
    2. TESTING (On-Demand): Enables remote triggering from Rhesis platform

    Args:
        name: Optional function name for registration (defaults to function.__name__)
        request_template: Manual input mappings (standard field → function param)
            Example: {"user_message": "{{ input }}", "conv_id": "{{ session_id }}"}
        response_mappings: Manual output mappings (function output → standard field)
            Example: {"output": "$.result.text", "session_id": "$.conv_id"}
        **metadata: Additional metadata about the function

    Returns:
        Decorated function

    Examples:
        # Auto-mapping (most common - no manual config needed)
        @collaborate()
        def chat(input: str, session_id: str = None):
            return {"output": "...", "session_id": session_id}

        # Manual override (custom naming)
        @collaborate(
            request_template={
                "user_query": "{{ input }}",
                "conv_id": "{{ session_id }}",
                "docs": "{{ context }}"
            },
            response_mappings={
                "output": "{{ jsonpath('$.result.text') }}",
                "session_id": "$.conv_id",
                "context": "$.sources"
            }
        )
        def chat(user_query: str, conv_id: str = None, docs: list = None):
            return {"result": {"text": "..."}, "conv_id": conv_id, "sources": [...]}

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
        if request_template:
            enriched_metadata["request_template"] = request_template
        if response_mappings:
            enriched_metadata["response_mappings"] = response_mappings

        # Lazy connector initialization happens here
        _default_client.register_collaborative_function(func_name, func, enriched_metadata)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Delegate tracing to connector manager
            if _default_client._connector_manager:
                return _default_client._connector_manager.trace_execution(
                    func_name, func, args, kwargs
                )
            # Fallback: just execute function without tracing
            return func(*args, **kwargs)

        return wrapper

    return decorator
