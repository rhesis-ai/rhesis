## TODO - move this file to the backend
from functools import wraps
from typing import Any, Callable, Dict, ParamSpec, TypeVar

import tenacity

P = ParamSpec("P")
T = TypeVar("T")


def sdk_config_to_backend_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if config.get("passing_categories"):
        config["reference_score"] = config.get("passing_categories")[0]
    else:
        config["reference_score"] = None

    # Convert metric_scope enum values to strings for backend
    if config.get("metric_scope"):
        config["metric_scope"] = [
            scope.value if hasattr(scope, "value") else str(scope)
            for scope in config["metric_scope"]
        ]

    # Convert backend enum to string for backend API
    if config.get("backend"):
        backend = config["backend"]
        config["backend_type"] = backend.value if hasattr(backend, "value") else str(backend)
        # Remove the old backend field as backend expects backend_type
        config.pop("backend", None)

    # Convert metric_type enum to string for backend API
    if config.get("metric_type"):
        metric_type = config["metric_type"]
        config["metric_type"] = (
            metric_type.value if hasattr(metric_type, "value") else str(metric_type)
        )

    return config


def backend_config_to_sdk_config(config: Dict[str, Any]) -> Dict[str, Any]:
    config["requires_ground_truth"] = config.pop("ground_truth_required", None)
    config["requires_context"] = config.pop("context_required", None)

    # Convert metric_scope strings back to enum values for SDK
    if config.get("metric_scope"):
        from rhesis.sdk.metrics.base import MetricScope

        config["metric_scope"] = [MetricScope(scope) for scope in config["metric_scope"]]

    # Convert backend_type back to backend enum for SDK
    if config.get("backend_type"):
        from rhesis.sdk.metrics.base import Backend

        backend_type = config.pop("backend_type")
        if isinstance(backend_type, dict) and "type_value" in backend_type:
            # Handle nested backend_type structure from API
            config["backend"] = Backend(backend_type["type_value"])
        else:
            # Handle simple string backend_type
            config["backend"] = Backend(backend_type)

    # Convert metric_type strings back to enum values for SDK
    if config.get("metric_type"):
        from rhesis.sdk.metrics.base import MetricType

        metric_type = config["metric_type"]
        if isinstance(metric_type, dict) and "type_value" in metric_type:
            # Handle nested metric_type structure from API
            config["metric_type"] = MetricType(metric_type["type_value"])
        else:
            # Handle simple string metric_type
            config["metric_type"] = MetricType(metric_type)

    return config


def retry_evaluation(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    retry_backoff: float = 2.0,
    retry_max_delay: float = 30.0,
    retry_exceptions: tuple = (ConnectionError, TimeoutError),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that adds retry logic to evaluation methods.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        retry_backoff: Exponential backoff multiplier
        retry_max_delay: Maximum delay between retries
        retry_exceptions: Exception types that should trigger a retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            @tenacity.retry(
                stop=tenacity.stop_after_attempt(max_retries),
                wait=tenacity.wait_exponential(
                    multiplier=retry_delay, exp_base=retry_backoff, max=retry_max_delay
                ),
                retry=tenacity.retry_if_exception_type(retry_exceptions),
            )
            def _execute_with_retry() -> T:
                return func(*args, **kwargs)

            return _execute_with_retry()

        return wrapper

    return decorator
