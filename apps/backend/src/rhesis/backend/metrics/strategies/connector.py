"""
Connector strategy for metric evaluation.

Handles metrics with backend="sdk" by dispatching evaluation requests
through the injected async WebSocket connector sender (RPC).  All connector
evaluation logic lives here.
"""

import asyncio
import concurrent.futures
import json
import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional

from rhesis.backend.app.usage_attribution import with_usage_attribution
from rhesis.backend.metrics.inputs import EvaluationInputs
from rhesis.backend.metrics.result_builder import MetricResultBuilder
from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
from rhesis.backend.metrics.strategies.base import OnMetricComplete
from rhesis.sdk.metrics import MetricConfig

logger = logging.getLogger(__name__)

# Timeout for a single connector metric call when run from a sync context
CONNECTOR_METRIC_CALL_TIMEOUT = 60

# Type alias for the async connector metric sender.
# Signature: (metric_run_id, metric_name, inputs) -> result dict
ConnectorMetricSender = Callable[
    [str, str, Dict[str, Any]],
    Awaitable[Dict[str, Any]],
]


class ConnectorStrategy:
    """Evaluates metrics via the WebSocket connector RPC (backend="sdk").

    When no sender is configured the strategy returns error results for
    every config rather than raising, so the evaluator can still return
    partial results from other strategies.
    """

    def __init__(
        self,
        connector_metric_sender: Optional[ConnectorMetricSender] = None,
        score_evaluator: Optional[ScoreEvaluator] = None,
    ) -> None:
        self._connector_metric_sender = connector_metric_sender
        self._score_evaluator = score_evaluator or ScoreEvaluator()

    def backend_value(self) -> str:
        return "sdk"

    def evaluate(
        self,
        configs: List[MetricConfig],
        inputs: EvaluationInputs,
        *,
        max_workers: int = 5,
    ) -> Dict[str, Any]:
        """Evaluate connector strategy configs via WebSocket RPC."""
        if not configs:
            return {}

        if not self._connector_metric_sender:
            logger.warning(
                "Cannot evaluate connector metrics: no connector_metric_sender configured"
            )
            return _build_sender_not_configured_results(configs)

        return _evaluate_connector_metrics(
            configs, inputs, self._connector_metric_sender, self._score_evaluator
        )

    async def a_evaluate(
        self,
        configs: List[MetricConfig],
        inputs: EvaluationInputs,
        *,
        on_metric_complete: OnMetricComplete = None,
    ) -> Dict[str, Any]:
        """Async evaluate — dispatches all connector calls concurrently via asyncio.gather."""
        if not configs:
            return {}
        if not self._connector_metric_sender:
            logger.warning("Cannot evaluate connector metrics (async): no connector_metric_sender")
            return _build_sender_not_configured_results(configs)

        if any(_wants_trace(config) for config in configs):
            # A blocking database read and a large dump; once, off the event loop.
            await asyncio.to_thread(inputs.trace_json)

        async def _call_one(config: MetricConfig) -> tuple:
            metric_name = config.name or ""
            class_name = config.class_name or metric_name
            description = config.description or f"Connector metric: {class_name}"
            threshold = config.threshold if config.threshold is not None else 0.0
            metric_run_id = str(uuid.uuid4())

            try:
                raw_result = await self._connector_metric_sender(
                    metric_run_id, class_name, _connector_inputs(config, inputs)
                )
                result = _connector_response_to_result(
                    raw_result,
                    config,
                    metric_name,
                    class_name,
                    description,
                    threshold,
                    self._score_evaluator,
                )
            except Exception as e:
                logger.error(
                    f"Async connector metric '{class_name}' error: {e}",
                    exc_info=True,
                )
                result = MetricResultBuilder.error(
                    reason=f"Connector metric evaluation failed: {e}",
                    backend="sdk",
                    name=metric_name,
                    class_name=class_name,
                    description=description,
                    error=str(e),
                    error_type=type(e).__name__,
                    threshold=threshold,
                )
            key = metric_name or class_name
            if on_metric_complete:
                try:
                    on_metric_complete(key, result)
                except Exception:
                    pass
            return key, result

        pairs = await asyncio.gather(*(_call_one(c) for c in configs))
        return dict(pairs)


# ============================================================================
# MODULE-LEVEL HELPERS (connector evaluation pipeline)
# ============================================================================


def _wants_trace(config: MetricConfig) -> bool:
    """Whether the SDK function behind this metric declares ``trace``.

    Metric sync records the function's parameters under ``sdk_connection`` in
    ``evaluation_examples`` (``services/connector/handlers/metric_sync.py``).
    """
    try:
        data = json.loads(config.evaluation_examples or "")
    except (json.JSONDecodeError, TypeError):
        return False
    connection = data.get("sdk_connection") if isinstance(data, dict) else None
    accepted = connection.get("accepted_params") if isinstance(connection, dict) else None
    return isinstance(accepted, list) and "trace" in accepted


def _connector_inputs(config: MetricConfig, inputs: EvaluationInputs) -> Dict[str, Any]:
    """The inputs sent to one SDK metric. The trace, the largest input by far, goes only
    to a metric that asked for it."""
    payload: Dict[str, Any] = {
        "input": inputs.input_text,
        "output": inputs.output_text,
        "expected_output": inputs.expected_output or "",
        "context": inputs.context or [],
    }
    if _wants_trace(config):
        payload["trace"] = inputs.trace_json()
    return payload


def _evaluate_connector_metrics(
    configs: List[MetricConfig],
    inputs: EvaluationInputs,
    connector_metric_sender: ConnectorMetricSender,
    score_evaluator: ScoreEvaluator,
) -> Dict[str, Any]:
    """Evaluate connector-side metrics via the WebSocket RPC."""
    if not configs:
        return {}

    results: Dict[str, Any] = {}

    for config in configs:
        metric_name = config.name or ""
        class_name = config.class_name or metric_name
        description = config.description or f"Connector metric: {class_name}"
        threshold = config.threshold if config.threshold is not None else 0.0

        metric_run_id = str(uuid.uuid4())

        try:
            raw_result = _call_connector_sender(
                connector_metric_sender,
                metric_run_id,
                class_name,
                _connector_inputs(config, inputs),
            )
            result = _connector_response_to_result(
                raw_result,
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
                f"Error evaluating connector metric '{class_name}': {e}",
                exc_info=True,
            )
            results[metric_name or class_name] = MetricResultBuilder.error(
                reason=f"Connector metric evaluation failed: {e}",
                backend="sdk",
                name=metric_name,
                class_name=class_name,
                description=description,
                error=str(e),
                error_type=type(e).__name__,
                threshold=threshold,
            )

    return results


def _call_connector_sender(
    sender: ConnectorMetricSender,
    metric_run_id: str,
    class_name: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the async sender from a sync context; use thread pool if already in async."""
    coro = sender(metric_run_id, class_name, inputs)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            # with_usage_attribution: a plain submit() drops contextvars, so
            # any LLM call under this coroutine would emit usage with no org.
            return pool.submit(with_usage_attribution(asyncio.run), coro).result(
                timeout=CONNECTOR_METRIC_CALL_TIMEOUT
            )
    return asyncio.run(coro)


def _connector_response_to_result(
    raw_result: Dict[str, Any],
    config: MetricConfig,
    metric_name: str,
    class_name: str,
    description: str,
    threshold: float,
    score_evaluator: ScoreEvaluator,
) -> Dict[str, Any]:
    """Map a connector response dict to a MetricResultBuilder success/error dict."""
    if "error" in raw_result and "status" not in raw_result:
        return MetricResultBuilder.error(
            reason=raw_result.get("details", raw_result.get("error", "Unknown error")),
            backend="sdk",
            name=metric_name,
            class_name=class_name,
            description=description,
            error=raw_result.get("error"),
            threshold=threshold,
        )
    if raw_result.get("status") == "error":
        return MetricResultBuilder.error(
            reason=raw_result.get("error", "Connector metric error"),
            backend="sdk",
            name=metric_name,
            class_name=class_name,
            description=description,
            error=raw_result.get("error"),
            threshold=threshold,
            duration_ms=raw_result.get("duration_ms"),
        )

    score = raw_result.get("score", 0.0)
    details = raw_result.get("details", {})
    threshold_op = config.threshold_operator or ">="
    is_successful = score_evaluator.evaluate_score(
        score=score,
        threshold=threshold,
        threshold_operator=threshold_op,
    )
    return MetricResultBuilder.success(
        score=score,
        reason=details.get("reason", f"Connector metric score: {score}"),
        is_successful=is_successful,
        backend="sdk",
        name=metric_name,
        class_name=class_name,
        description=description,
        threshold=threshold,
        duration_ms=raw_result.get("duration_ms"),
    )


def _build_sender_not_configured_results(
    configs: List[MetricConfig],
) -> Dict[str, Any]:
    """Build error results for all configs when no connector sender is configured."""
    return {
        (c.name or f"ConnectorMetric_{i}"): MetricResultBuilder.error(
            reason="Connector metric sender not configured",
            backend="sdk",
            name=c.name or f"ConnectorMetric_{i}",
            class_name=c.class_name or "Unknown",
            error="connector_metric_sender not configured",
        )
        for i, c in enumerate(configs)
    }
