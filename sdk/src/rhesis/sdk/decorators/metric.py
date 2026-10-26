"""Metric decorator for registering functions as SDK-side metrics."""

import inspect
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from rhesis.sdk.connector.registry import METRIC_ALLOWED_PARAMS
from rhesis.sdk.metrics.arguments import (
    EVALUATION_PARAMETERS,
    REPLACED_PARAMETERS,
    TRACE_SHORTCUTS,
    evaluation_arguments,
)

from ._state import get_default_client, is_client_disabled

logger = logging.getLogger(__name__)


def _validate_metric_signature(func: Callable) -> list[str]:
    """
    Validate that a metric function has a valid signature.

    A metric declares any of ``input``, ``output``, ``trace`` and ``expectations``, and no
    other parameter names.

    Args:
        func: The function to validate

    Returns:
        List of accepted parameter names

    Raises:
        TypeError: If the signature is invalid
    """
    param_names = list(inspect.signature(func).parameters)
    allowed = ", ".join(EVALUATION_PARAMETERS)

    for name in param_names:
        if name in METRIC_ALLOWED_PARAMS:
            continue
        if name in REPLACED_PARAMETERS:
            raise TypeError(
                f"@metric function '{func.__name__}' declares '{name}', which metrics no "
                f"longer receive. Read {REPLACED_PARAMETERS[name]} instead. Allowed: {allowed}"
            )
        raise TypeError(
            f"@metric function '{func.__name__}' has invalid parameter '{name}'. Allowed: {allowed}"
        )
    if not param_names:
        raise TypeError(
            f"@metric function '{func.__name__}' declares no parameters. Declare any of: {allowed}"
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

    The function declares any of these parameters, and receives only those:
    - input (str): what the endpoint was sent
    - output (str): what it answered
    - trace (Trace): everything the endpoint did to answer, as a
      ``rhesis.sdk.entities.Trace`` with its spans loaded. ``trace.context``,
      ``trace.tool_calls`` and ``trace.metadata`` read the whole trace at once.
    - expectations (Expectations): what should have happened, from the test.
      ``expectations.response`` is the reference answer. None for production traces.

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

        @metric(score_type="binary")
        def exact_match(output: str, expectations: Expectations) -> dict:
            return {"score": float(output == expectations.response)}

        @metric(name="my_groundedness", score_type="binary")
        def groundedness(output: str, trace: Trace) -> dict:
            is_grounded = verify(output, trace.context)
            return {"score": 1.0 if is_grounded else 0.0}

        @metric(score_type="binary")
        def at_most_five_tool_calls(trace: Trace) -> dict:
            return {"score": 1.0 if len(trace.tool_calls) <= 5 else 0.0}
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

        # Turns expectations into Expectations and builds the trace from shortcuts, as for
        # every other metric, whether the connector calls the function or a script does.
        prepared = evaluation_arguments(func)
        passed = set(accepted_params) | set(TRACE_SHORTCUTS)

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def wrapper(**kwargs: Any) -> Any:
                return await prepared(**{k: v for k, v in kwargs.items() if k in passed})

            _default_client.register_metric(metric_name, wrapper, enriched_metadata)
            return wrapper

        @wraps(func)
        def wrapper(**kwargs: Any) -> Any:
            return prepared(**{k: v for k, v in kwargs.items() if k in passed})

        _default_client.register_metric(metric_name, wrapper, enriched_metadata)
        return wrapper

    return decorator
