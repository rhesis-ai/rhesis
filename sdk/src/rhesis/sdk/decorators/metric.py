"""Metric decorator for registering functions as SDK-side metrics."""

import inspect
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from rhesis.sdk.connector.registry import (
    METRIC_ALLOWED_PARAMS,
    METRIC_REQUIRED_PARAMS,
)

from ._state import get_default_client, is_client_disabled

logger = logging.getLogger(__name__)


def _validate_metric_signature(func: Callable) -> list[str]:
    """
    Validate that a metric function has a valid signature.

    Required: input, output
    Optional: expected_output, context
    No other parameter names are allowed.

    Args:
        func: The function to validate

    Returns:
        List of accepted parameter names

    Raises:
        TypeError: If the signature is invalid
    """
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())

    param_set = set(param_names)

    missing = METRIC_REQUIRED_PARAMS - param_set
    if missing:
        raise TypeError(
            f"@metric function '{func.__name__}' is missing required "
            f"parameter(s): {', '.join(sorted(missing))}. "
            f"Required: input, output"
        )

    extra = param_set - METRIC_ALLOWED_PARAMS
    if extra:
        raise TypeError(
            f"@metric function '{func.__name__}' has invalid "
            f"parameter(s): {', '.join(sorted(extra))}. "
            f"Allowed: input, output, expected_output, context"
        )

    return param_names


def metric(
    name: str | None = None,
    score_type: str = "numeric",
    description: str | None = None,
    **extra_metadata,
) -> Callable:
    """
    Decorator to register a function as an SDK-side metric.

    The decorated function is registered with the connector and can be
    invoked remotely by the backend during test evaluation.

    The function must accept a subset of these parameters:
    - input (str): required - the input/prompt text
    - output (str): required - the LLM response text
    - expected_output (str): optional - ground truth / reference output
    - context (List[str]): optional - context documents

    The function must return a dict with at least a "score" key,
    or a MetricResult instance.

    Args:
        name: Optional metric name (defaults to function.__name__)
        score_type: Score type: "numeric", "binary", or "categorical"
        description: Optional human-readable description
        **extra_metadata: Additional metadata passed to the backend

    Returns:
        Decorated function

    Examples:
        @metric()
        def toxicity(input: str, output: str) -> dict:
            score = check_toxicity(output)
            return {"score": score, "details": {"reason": "..."}}

        @metric(name="my_groundedness", score_type="binary")
        def groundedness(input: str, output: str, context: list[str]) -> dict:
            is_grounded = verify(output, context)
            return {"score": 1.0 if is_grounded else 0.0}
    """

    def decorator(func: Callable) -> Callable:
        if is_client_disabled():
            return func

        _default_client = get_default_client()
        if _default_client is None:
            raise RuntimeError(
                "RhesisClient not initialized. Create a RhesisClient instance "
                "before using @metric decorator."
            )

        accepted_params = _validate_metric_signature(func)
        metric_name = name or func.__name__

        enriched_metadata = {
            "score_type": score_type,
            "description": description or "",
            "class_name": metric_name,
            "accepted_params": accepted_params,
            **extra_metadata,
        }

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def wrapper(**kwargs: Any) -> Any:
                filtered = {k: v for k, v in kwargs.items() if k in accepted_params}
                return await func(**filtered)

            _default_client.register_metric(metric_name, wrapper, enriched_metadata)
            return wrapper

        @wraps(func)
        def wrapper(**kwargs: Any) -> Any:
            filtered = {k: v for k, v in kwargs.items() if k in accepted_params}
            return func(**filtered)

        _default_client.register_metric(metric_name, wrapper, enriched_metadata)
        return wrapper

    return decorator
