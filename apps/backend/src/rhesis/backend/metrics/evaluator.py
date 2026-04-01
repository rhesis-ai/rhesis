import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.metrics.metric_config import validate_metric_configs
from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
from rhesis.backend.metrics.strategies.base import MetricStrategy
from rhesis.backend.metrics.strategies.connector import (
    ConnectorMetricSender,
    ConnectorStrategy,
)
from rhesis.backend.metrics.strategies.local import LocalStrategy
from rhesis.sdk.metrics import MetricConfig
from rhesis.sdk.metrics.conversational.types import ConversationHistory

logger = logging.getLogger(__name__)


class MetricEvaluator:
    """Evaluator that dispatches metric computation to registered backend strategies.

    Responsibilities (SRP):
      - Validate and normalize raw metric configs.
      - Group configs by their backend identifier.
      - Dispatch each group to the matching strategy.
      - Merge results and return.

    Adding a new strategy requires only a new :class:`MetricStrategy`
    implementation and registering it – ``evaluate()`` is never modified.
    """

    def __init__(
        self,
        model: Optional[Any] = None,
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
        connector_metric_sender: Optional[ConnectorMetricSender] = None,
        extra_strategies: Optional[List[MetricStrategy]] = None,
    ) -> None:
        """
        Initialize evaluator with optional backend strategy overrides.

        Args:
            model: Optional default LLM model for local metric evaluation.
            db: Optional database session for fetching metric-specific models.
            organization_id: Optional organization ID for secure model lookups.
            connector_metric_sender: Optional async callable for connector-backend metrics.
                Signature: (metric_run_id, metric_name, inputs) -> result dict.
                When *None*, connector-backend metrics return error results.
            extra_strategies: Optional additional (or replacement) strategies.
                Each strategy is registered by its ``backend_value()``.  Use
                this for testing or to add custom backends without subclassing.
        """
        score_evaluator = ScoreEvaluator()

        self._local_strategy: MetricStrategy = LocalStrategy(
            model=model,
            db=db,
            organization_id=organization_id,
            score_evaluator=score_evaluator,
        )

        self._connector_strategy: MetricStrategy = ConnectorStrategy(
            connector_metric_sender=connector_metric_sender,
            score_evaluator=score_evaluator,
        )

        # Build the named strategy registry (backend_value -> strategy)
        self._strategies: Dict[str, MetricStrategy] = {
            self._local_strategy.backend_value(): self._local_strategy,
            self._connector_strategy.backend_value(): self._connector_strategy,
        }

        if extra_strategies:
            for strategy in extra_strategies:
                self._strategies[strategy.backend_value()] = strategy

    @staticmethod
    def _group_by_backend(
        metric_configs: List[MetricConfig],
    ) -> "Dict[str, List[MetricConfig]]":
        """Group validated MetricConfig objects by their backend identifier."""
        groups: Dict[str, List[MetricConfig]] = {}
        for config in metric_configs:
            raw = getattr(config.backend, "value", config.backend)
            backend_val: str = raw if isinstance(raw, str) else "__local__"
            groups.setdefault(backend_val, []).append(config)
        return groups

    def evaluate(
        self,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        metrics: List[Union[Dict[str, Any], MetricConfig, MetricModel]],
        max_workers: int = 5,
        conversation_history: Optional[ConversationHistory] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Compute metrics using the configured backends.

        Args:
            input_text: The input query or question.
            output_text: The actual output from the LLM.
            expected_output: The expected or reference output.
            context: List of context strings used for the response.
            metrics: List of Metric models, MetricConfig objects, or config dicts.
            max_workers: Maximum number of parallel workers for local strategy.
            conversation_history: Optional conversation history.
            metadata: Optional metadata dict.
            tool_calls: Optional list of tool calls made by the endpoint.

        Returns:
            Dictionary containing scores and details for each metric.
        """
        if not metrics:
            logger.warning("No metrics provided for evaluation")
            return {}

        # Step 1: validate and normalize raw configs
        metric_configs, invalid_metric_results = validate_metric_configs(metrics)

        if not metric_configs:
            logger.warning("No valid metrics found after parsing")
            if invalid_metric_results:
                logger.warning(
                    f"Returning {len(invalid_metric_results)} invalid metrics as error results"
                )
                return invalid_metric_results
            logger.warning("No metrics found at all, returning empty results")
            return {}

        # Step 2: group configs by backend
        configs_by_backend = self._group_by_backend(metric_configs)

        # Step 3: dispatch each group to the matching strategy
        results: Dict[str, Any] = {}
        for backend_val, backend_configs in configs_by_backend.items():
            strategy = self._strategies.get(backend_val, self._local_strategy)
            backend_results = strategy.evaluate(
                backend_configs,
                input_text,
                output_text,
                expected_output,
                context,
                max_workers=max_workers,
                conversation_history=conversation_history,
                metadata=metadata,
                tool_calls=tool_calls,
            )
            results.update(backend_results)

        # Step 4: merge invalid metric results
        results.update(invalid_metric_results)

        return results

    async def a_evaluate(
        self,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        metrics: List[Union[Dict[str, Any], MetricConfig, MetricModel]],
        conversation_history: Optional[ConversationHistory] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Async version of evaluate — dispatches backends concurrently."""
        if not metrics:
            logger.warning("No metrics provided for async evaluation")
            return {}

        metric_configs, invalid_metric_results = validate_metric_configs(metrics)

        if not metric_configs:
            logger.warning("No valid metrics found after parsing (async)")
            return invalid_metric_results or {}

        configs_by_backend = self._group_by_backend(metric_configs)

        async def _run_backend(backend_val: str, backend_configs: list) -> Dict[str, Any]:
            strategy = self._strategies.get(backend_val, self._local_strategy)
            return await strategy.a_evaluate(
                backend_configs,
                input_text,
                output_text,
                expected_output,
                context,
                conversation_history=conversation_history,
                metadata=metadata,
                tool_calls=tool_calls,
            )

        backend_results = await asyncio.gather(
            *[
                _run_backend(bv, bc)
                for bv, bc in configs_by_backend.items()
            ],
            return_exceptions=True,
        )

        results: Dict[str, Any] = {}
        for bv, br in zip(configs_by_backend.keys(), backend_results):
            if isinstance(br, Exception):
                logger.error(f"Backend '{bv}' async evaluation failed: {br}")
                continue
            results.update(br)

        results.update(invalid_metric_results)
        return results
