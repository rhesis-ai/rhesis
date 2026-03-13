"""
SDK metric evaluation via connector RPC.

Evaluates metrics that run in the SDK (backend="sdk") by sending
evaluation requests through the injected async sender and building
result dicts for the orchestrator.
"""

import asyncio
import concurrent.futures
import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, List

from rhesis.backend.metrics.result_builder import MetricResultBuilder
from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
from rhesis.sdk.metrics import MetricConfig

logger = logging.getLogger(__name__)

# Timeout for a single SDK metric call when run from a sync context
SDK_METRIC_CALL_TIMEOUT = 60


# Type alias for the async SDK metric sender.
# Signature: (metric_run_id, metric_name, inputs) -> result dict
SdkMetricSender = Callable[
    [str, str, Dict[str, Any]],
    Awaitable[Dict[str, Any]],
]


def evaluate_sdk_metrics(
    sdk_configs: List[MetricConfig],
    input_text: str,
    output_text: str,
    expected_output: str,
    context: List[str],
    sdk_metric_sender: SdkMetricSender,
    score_evaluator: ScoreEvaluator,
) -> Dict[str, Any]:
    """
    Evaluate SDK-side metrics via the connector RPC.

    Args:
        sdk_configs: List of metric configurations with backend="sdk"
        input_text: The input query
        output_text: The actual LLM output
        expected_output: The expected output
        context: List of context strings
        sdk_metric_sender: Async callable (metric_run_id, class_name, inputs) -> result dict
        score_evaluator: Evaluator for threshold / is_successful

    Returns:
        Dictionary of metric results keyed by metric name
    """
    if not sdk_configs:
        return {}

    results: Dict[str, Any] = {}

    for config in sdk_configs:
        metric_name = config.name or ""
        class_name = config.class_name or metric_name
        description = config.description or f"SDK metric: {class_name}"
        threshold = config.threshold if config.threshold is not None else 0.0

        metric_run_id = str(uuid.uuid4())
        inputs = {
            "input": input_text,
            "output": output_text,
            "expected_output": expected_output or "",
            "context": context or [],
        }

        try:
            sdk_result = _call_sdk_sender(
                sdk_metric_sender, metric_run_id, class_name, inputs
            )
            result = _sdk_response_to_result(
                sdk_result,
                config,
                metric_name,
                class_name,
                description,
                threshold,
                score_evaluator,
            )
            results[metric_name or class_name] = result
        except Exception as e:
            logger.error(
                f"Error evaluating SDK metric '{class_name}': {e}",
                exc_info=True,
            )
            results[metric_name or class_name] = MetricResultBuilder.error(
                reason=f"SDK metric evaluation failed: {e}",
                backend="sdk",
                name=metric_name,
                class_name=class_name,
                description=description,
                error=str(e),
                error_type=type(e).__name__,
                threshold=threshold,
            )

    return results


def _call_sdk_sender(
    sender: SdkMetricSender,
    metric_run_id: str,
    class_name: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the async sender from sync context; use thread pool if already in async."""
    coro = sender(metric_run_id, class_name, inputs)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result(timeout=SDK_METRIC_CALL_TIMEOUT)
    return asyncio.run(coro)


def _sdk_response_to_result(
    sdk_result: Dict[str, Any],
    config: MetricConfig,
    metric_name: str,
    class_name: str,
    description: str,
    threshold: float,
    score_evaluator: ScoreEvaluator,
) -> Dict[str, Any]:
    """Map SDK response dict to MetricResultBuilder success/error dict."""
    if "error" in sdk_result and "status" not in sdk_result:
        return MetricResultBuilder.error(
            reason=sdk_result.get("details", sdk_result.get("error", "Unknown error")),
            backend="sdk",
            name=metric_name,
            class_name=class_name,
            description=description,
            error=sdk_result.get("error"),
            threshold=threshold,
        )
    if sdk_result.get("status") == "error":
        return MetricResultBuilder.error(
            reason=sdk_result.get("error", "SDK metric error"),
            backend="sdk",
            name=metric_name,
            class_name=class_name,
            description=description,
            error=sdk_result.get("error"),
            threshold=threshold,
            duration_ms=sdk_result.get("duration_ms"),
        )

    score = sdk_result.get("score", 0.0)
    details = sdk_result.get("details", {})
    threshold_op = config.threshold_operator or ">="
    is_successful = score_evaluator.evaluate_score(
        score=score,
        threshold=threshold,
        threshold_operator=threshold_op,
    )
    return MetricResultBuilder.success(
        score=score,
        reason=details.get("reason", f"SDK metric score: {score}"),
        is_successful=is_successful,
        backend="sdk",
        name=metric_name,
        class_name=class_name,
        description=description,
        threshold=threshold,
        duration_ms=sdk_result.get("duration_ms"),
    )


def build_sender_not_configured_results(
    sdk_configs: List[MetricConfig],
) -> Dict[str, Any]:
    """
    Build error results for all SDK configs when no sender is configured.

    Returns:
        Dictionary of error result dicts keyed by metric name
    """
    return {
        (c.name or f"SDKMetric_{i}"): MetricResultBuilder.error(
            reason="SDK metric sender not configured",
            backend="sdk",
            name=c.name or f"SDKMetric_{i}",
            class_name=c.class_name or "Unknown",
            error="sdk_metric_sender not configured",
        )
        for i, c in enumerate(sdk_configs)
    }
