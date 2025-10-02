## TODO - move this file to the backend
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

import tenacity

from rhesis.sdk.metrics.base import F, MetricConfig


def sdk_config_to_backend_config(config: Dict[str, Any]) -> Dict[str, Any]:
    config["min_score"] = config["parameters"].get("min_score")
    config["max_score"] = config["parameters"].get("max_score")
    config["threshold"] = config["parameters"].get("threshold")
    config["threshold_operator"] = config["parameters"].get("threshold_operator")
    if config["parameters"].get("passing_categories"):
        config["reference_score"] = config["parameters"].get("passing_categories")[0]
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


def run_evaluation(
    input_text: str,
    output_text: str,
    expected_output: Optional[str],
    context: List[str],
    metrics: List[Union[Dict[str, Any], MetricConfig]],
    max_workers: int = 5,
) -> Dict[str, Any]:
    """
    Helper function to run the metric evaluation using MetricEvaluator.

    Args:
        input_text: The input query or question
        output_text: The actual output from the LLM
        expected_output: The expected or reference output
        context: List of context strings used for the response
        metrics: List of metric configurations (MetricConfig objects or dictionaries)
        max_workers: Maximum number of parallel workers

    Returns:
        Dictionary of metric results
    """
    # Lazy import to avoid circular dependencies
    from rhesis.sdk.metrics.evaluator import MetricEvaluator

    evaluator = MetricEvaluator()
    return evaluator.evaluate(
        input_text=input_text,
        output_text=output_text,
        expected_output=expected_output,
        context=context,
        metrics=metrics,
        max_workers=max_workers,
    )


def diagnose_invalid_metric(config: Union[Dict[str, Any], MetricConfig]) -> str:
    """
    Diagnose the reason why a metric configuration is invalid.

    Args:
        config: The metric configuration

    Returns:
        A string describing the reason why the metric configuration is invalid
    """
    if config is None:
        return "configuration is None"

    if isinstance(config, MetricConfig):
        missing_fields = []
        if not config.class_name or (
            isinstance(config.class_name, str) and not config.class_name.strip()
        ):
            missing_fields.append("class_name")
        if not config.backend or (isinstance(config.backend, str) and not config.backend.strip()):
            missing_fields.append("backend")
        if missing_fields:
            return f"missing or empty required fields: {', '.join(missing_fields)}"
    elif isinstance(config, dict):
        missing_fields = []
        if (
            "class_name" not in config
            or config["class_name"] is None
            or (isinstance(config["class_name"], str) and not config["class_name"].strip())
        ):
            missing_fields.append("class_name")
        if (
            "backend" not in config
            or config["backend"] is None
            or (isinstance(config["backend"], str) and not config["backend"].strip())
        ):
            missing_fields.append("backend")
        if missing_fields:
            return f"missing or empty required fields: {', '.join(missing_fields)}"
    else:
        return (
            f"invalid configuration type: {type(config).__name__} (expected dict or MetricConfig)"
        )

    return "unknown validation error"


def retry_evaluation(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    retry_backoff: float = 2.0,
    retry_max_delay: float = 30.0,
    retry_exceptions: tuple = (ConnectionError, TimeoutError),
) -> Callable[[F], F]:
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

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            @tenacity.retry(
                stop=tenacity.stop_after_attempt(max_retries),
                wait=tenacity.wait_exponential(
                    multiplier=retry_delay, exp_base=retry_backoff, max=retry_max_delay
                ),
                retry=tenacity.retry_if_exception_type(retry_exceptions),
            )
            def _execute_with_retry():
                return func(*args, **kwargs)

            return _execute_with_retry()

        return wrapper

    return decorator
