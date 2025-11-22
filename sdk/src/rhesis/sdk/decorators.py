"""Decorators for collaborative testing."""

import time
from functools import wraps
from typing import Any, Callable, Optional

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


def _send_trace_async(
    client: "Client",  # noqa: F821
    function_name: str,
    inputs: dict,
    output: Any,
    duration_ms: float,
    status: str,
    error: Optional[str] = None,
) -> None:
    """
    Send trace to backend asynchronously (non-blocking).

    Args:
        client: RhesisClient instance
        function_name: Name of the function
        inputs: Function inputs
        output: Function output
        duration_ms: Execution duration in milliseconds
        status: "success" or "error"
        error: Error message if status is "error"
    """
    import logging

    import requests

    logger = logging.getLogger(__name__)

    try:
        # Send trace via HTTP POST (non-blocking)
        trace_data = {
            "function_name": function_name,
            "inputs": inputs,
            "output": str(output) if output is not None else None,
            "duration_ms": duration_ms,
            "status": status,
            "error": error,
            "timestamp": time.time(),
            "project_id": client.project_id,
            "environment": client.environment,
        }

        # Send to backend trace endpoint
        url = f"{client._base_url}/connector/trace"
        headers = {
            "Authorization": f"Bearer {client.api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(f"📤 Sending trace to {url}")
        logger.debug(
            f"   Function: {function_name}, Status: {status}, Duration: {duration_ms:.2f}ms"
        )

        # Non-blocking request with short timeout
        response = requests.post(url, json=trace_data, headers=headers, timeout=2)
        response.raise_for_status()

        logger.debug(f"✅ Trace sent successfully: {response.status_code}")
    except Exception as e:
        # Log but don't break the application
        logger.warning(f"⚠️ Failed to send trace: {e}")
        pass


def collaborate(name: Optional[str] = None, **metadata) -> Callable:
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
            import inspect
            import logging
            import threading

            logger = logging.getLogger(__name__)

            # Trace execution
            start_time = time.time()
            inputs = {"args": args, "kwargs": kwargs}

            try:
                # Call original function
                result = func(*args, **kwargs)

                # Check if result is a generator
                if inspect.isgenerator(result):
                    logger.debug(f"🔄 {func_name} returned a generator - wrapping for tracing")

                    # Wrap generator to capture output
                    def traced_generator():
                        collected_output = []
                        try:
                            for item in result:
                                collected_output.append(str(item))
                                yield item
                            # Generator completed successfully
                            duration_ms = (time.time() - start_time) * 1000
                            output = "".join(collected_output)
                            thread = threading.Thread(
                                target=_send_trace_async,
                                args=(
                                    _default_client,
                                    func_name,
                                    inputs,
                                    output,
                                    duration_ms,
                                    "success",
                                ),
                                daemon=True,
                            )
                            thread.start()
                        except Exception as e:
                            # Generator failed
                            duration_ms = (time.time() - start_time) * 1000
                            thread = threading.Thread(
                                target=_send_trace_async,
                                args=(
                                    _default_client,
                                    func_name,
                                    inputs,
                                    None,
                                    duration_ms,
                                    "error",
                                    str(e),
                                ),
                                daemon=True,
                            )
                            thread.start()
                            raise

                    return traced_generator()
                else:
                    # Non-generator result
                    duration_ms = (time.time() - start_time) * 1000

                    # Send trace asynchronously (non-blocking)
                    thread = threading.Thread(
                        target=_send_trace_async,
                        args=(
                            _default_client,
                            func_name,
                            inputs,
                            result,
                            duration_ms,
                            "success",
                        ),
                        daemon=True,
                    )
                    thread.start()

                    return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                # Send error trace asynchronously (non-blocking)
                thread = threading.Thread(
                    target=_send_trace_async,
                    args=(
                        _default_client,
                        func_name,
                        inputs,
                        None,
                        duration_ms,
                        "error",
                        str(e),
                    ),
                    daemon=True,
                )
                thread.start()

                # Re-raise the exception
                raise

        return wrapper

    return decorator
