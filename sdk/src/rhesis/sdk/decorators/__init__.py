"""
Rhesis SDK decorators for observability and endpoint registration.

This module provides decorators for:
- Function observability with OpenTelemetry (@observe)
- Endpoint registration for remote testing (@endpoint)
- Custom observer builders for domain-specific patterns

Backward compatible imports:
    from rhesis.sdk import observe, endpoint
    from rhesis.sdk.decorators import create_observer, ObserverBuilder
"""

from typing import Any, Callable

# Re-export for backward compatibility
# Import _state module itself for test monkeypatching
from . import _state
from ._state import _register_default_client, get_default_client, is_client_disabled
from .builders import ObserverBuilder, create_observer
from .endpoint import collaborate, endpoint
from .observe import observe


def bind_context(func: Callable, *args: Any, **kwargs: Any) -> Callable:
    """
    Helper to bind a context manager or generator function with arguments.

    This is a convenience wrapper for creating fresh context managers per function call
    in @endpoint bind parameters. It's clearer than using functools.partial and makes
    the intent explicit.

    Args:
        func: A context manager function (decorated with @contextmanager) or generator
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        A callable that creates a fresh context manager when invoked

    Examples:
        # Binding a database session with tenant context
        @endpoint(bind={
            "db": bind_context(get_db_with_tenant_variables, org_id, user_id)
        })
        def my_function(db, input: str):
            return {"output": db.query(input)}

        # Binding configuration with parameters
        @endpoint(bind={
            "config": bind_context(get_config, env="production", debug=False)
        })
        def my_function(config, input: str):
            return {"output": config.process(input)}

    Note:
        This is equivalent to: lambda: func(*args, **kwargs)
        But more explicit and self-documenting.
    """
    return lambda: func(*args, **kwargs)


__all__ = [
    # Decorators
    "observe",
    "endpoint",
    "collaborate",
    # Builders
    "create_observer",
    "ObserverBuilder",
    # Utilities
    "bind_context",
    # Internal (for SDK use)
    "_register_default_client",
    "get_default_client",
    "is_client_disabled",
    "_state",
]
