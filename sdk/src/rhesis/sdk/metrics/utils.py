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

    return config


def backend_config_to_sdk_config(config: Dict[str, Any]) -> Dict[str, Any]:
    keys_to_remove = [
        "id",
        "nano_id",
        "explanation",
        "metric_type_id",
        "backend_type_id",
        "model_id",
        "status_id",
        "assignee_id",
        "owner_id",
        "organization_id",
        "user_id",
        "created_at",
        "updated_at",
        "tags",
        "status",
        "assignee",
        "owner",
        "model",
        "behaviors",
        "comments",
        "organization",
        "user",
        "backend_type",
        "counts",
    ]
    for key in keys_to_remove:
        config.pop(key, None)

    config["parameters"] = {}
    config["parameters"]["min_score"] = config.pop("min_score", None)
    config["parameters"]["max_score"] = config.pop("max_score", None)
    config["parameters"]["threshold"] = config.pop("threshold", None)
    config["parameters"]["threshold_operator"] = config.pop("threshold_operator", None)
    config["parameters"]["reference_score"] = config.pop("reference_score", None)
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
