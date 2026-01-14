"""Endpoint decorator for registering functions as Rhesis endpoints."""

import inspect
from collections.abc import Callable
from functools import wraps

from ._state import get_default_client, is_client_disabled


def endpoint(
    name: str | None = None,
    request_mapping: dict | None = None,
    response_mapping: dict | None = None,
    span_name: str | None = None,
    observe: bool = True,
    bind: dict | None = None,
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
        bind: Infrastructure dependencies to inject into the function (optional)
            Binds parameters that won't appear in the remote function signature.
            Useful for database connections, auth context, configuration, etc.
            Supports both static values and callables (evaluated at call time).
            Example: {
                "db": lambda: get_db_session(),  # Fresh connection per call
                "config": AppConfig(),           # Static singleton
                "user": lambda: get_current_user()  # Runtime context
            }
            Bound parameters are:
            - Excluded from the registered function signature
            - Automatically injected when the function is called
            - Evaluated at call time if callable, used directly if static
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

        # Example 5: Binding infrastructure dependencies
        @endpoint(
            bind={
                "db": lambda: get_db_session(),  # Fresh session per call
                "config": AppConfig(),           # Static singleton
            }
        )
        def query_data(db, config, input: str) -> dict:
            # db and config are injected, only input appears in remote signature
            results = db.query(config.table, input)
            return {"output": format_results(results)}

        # Example 6: Binding with FastAPI-style generator dependencies
        def get_db():
            '''Generator that yields database session with auto-cleanup'''
            with database.get_session() as session:
                yield session
                # Cleanup happens automatically

        @endpoint(
            bind={
                "db": get_db,  # Generator-based dependency (auto-cleanup)
                "user": lambda: get_current_user_context(),
            }
        )
        async def authenticated_query(db, user, input: str) -> dict:
            # Database connection is automatically closed after execution
            if not user.is_authenticated:
                return {"output": "Unauthorized"}
            return {"output": db.query_for_user(user.id, input)}

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
        # If client is disabled, return the original function unmodified
        # This completely bypasses all decorator overhead
        if is_client_disabled():
            return func

        _default_client = get_default_client()
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

        # Store bound parameters and exclusion list
        if bind:
            enriched_metadata["_bound_params"] = list(bind.keys())

        # Get function signature to map positional args to parameter names
        func_sig = inspect.signature(func)
        param_names = list(func_sig.parameters.keys())

        # Helper to inject bound parameters
        def inject_bound_params(args, kwargs):
            """
            Inject bound parameters into kwargs, handling generators as context managers.

            This function detects generator-based dependencies (like FastAPI's Depends
            with yield) and properly manages their lifecycle. Generators are advanced to
            get their yielded value, and the generator objects are returned for cleanup
            after the function executes.

            Args:
                args: Positional arguments passed to the function
                kwargs: Keyword arguments passed to the function

            Returns:
                tuple: (injected_kwargs, cleanup_generators)
                    - injected_kwargs: kwargs with bound parameters injected
                    - cleanup_generators: list of generators that need cleanup for
                      resource management
            """
            if not bind:
                return kwargs, []

            # Determine which parameters are already provided
            provided_params = set(kwargs.keys())

            # Map positional args to parameter names
            for i, arg_value in enumerate(args):
                if i < len(param_names):
                    provided_params.add(param_names[i])

            injected_kwargs = kwargs.copy()
            cleanup_generators = []

            for param_name, param_value in bind.items():
                # Don't inject if already provided (either as positional arg or kwarg)
                if param_name not in provided_params:
                    # Call if callable, use directly otherwise
                    if callable(param_value):
                        result = param_value()

                        # Check if it's a generator (context manager-like dependency)
                        if inspect.isgenerator(result):
                            # Get the yielded value (the actual dependency)
                            injected_kwargs[param_name] = next(result)
                            # Store generator for cleanup (will trigger finally block)
                            cleanup_generators.append(result)
                        else:
                            injected_kwargs[param_name] = result
                    else:
                        injected_kwargs[param_name] = param_value

            return injected_kwargs, cleanup_generators

        # Helper to select appropriate tracer (connector manager takes precedence)
        def get_tracer_method(is_async: bool):
            """Get the appropriate trace execution method."""
            if _default_client._connector_manager:
                return (
                    _default_client._connector_manager.trace_execution_async
                    if is_async
                    else _default_client._connector_manager.trace_execution
                )
            return (
                _default_client._tracer.trace_execution_async
                if is_async
                else _default_client._tracer.trace_execution
            )

        # Handle async functions
        if inspect.iscoroutinefunction(func):
            trace_func = get_tracer_method(is_async=True)

            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Inject bound parameters and get generators that need cleanup
                kwargs, cleanup_generators = inject_bound_params(args, kwargs)

                try:
                    if not observe:
                        return await func(*args, **kwargs)
                    return await trace_func(func_name, func, args, kwargs, span_name)
                finally:
                    # Cleanup all generators (closes database connections, file handles, etc.)
                    for gen in cleanup_generators:
                        try:
                            # Advance generator to trigger finally block and cleanup
                            next(gen)
                        except StopIteration:
                            # Expected - generator is exhausted after cleanup
                            pass
                        except Exception as e:
                            # Log cleanup errors but don't fail the request
                            # This prevents cleanup errors from masking the actual response
                            import logging

                            logging.warning(f"Error cleaning up generator dependency: {e}")

            _default_client.register_endpoint(func_name, wrapper, enriched_metadata)
            return wrapper

        # Handle sync functions
        trace_func = get_tracer_method(is_async=False)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Inject bound parameters and get generators that need cleanup
            kwargs, cleanup_generators = inject_bound_params(args, kwargs)

            try:
                if not observe:
                    return func(*args, **kwargs)
                return trace_func(func_name, func, args, kwargs, span_name)
            finally:
                # Cleanup all generators (closes database connections, file handles, etc.)
                for gen in cleanup_generators:
                    try:
                        # Advance generator to trigger finally block and cleanup
                        next(gen)
                    except StopIteration:
                        # Expected - generator is exhausted after cleanup
                        pass
                    except Exception as e:
                        # Log cleanup errors but don't fail the request
                        # This prevents cleanup errors from masking the actual response
                        import logging

                        logging.warning(f"Error cleaning up generator dependency: {e}")

        _default_client.register_endpoint(func_name, wrapper, enriched_metadata)
        return wrapper

    return decorator


# Backwards compatibility alias
collaborate = endpoint
