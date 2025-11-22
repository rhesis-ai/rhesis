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


def collaborate(name: str | None = None, **metadata) -> Callable:
    """
    Decorator for collaborative testing and observability.

    This decorator enables two features:
    1. TRACING (Always On): Traces all normal executions and sends to backend
    2. TESTING (On-Demand): Enables remote triggering from Rhesis platform

    Args:
        name: Optional function name for registration (defaults to function.__name__)
        **metadata: Additional metadata about the function

    Returns:
        Decorated function

    Example:
        @collaborate(name="my_func", tags=["production"])
        def my_func(input: str) -> dict:
            return {"result": input.upper()}

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

        # Lazy connector initialization happens here
        _default_client.register_collaborative_function(func_name, func, metadata)

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
