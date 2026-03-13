import logging
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from rhesis.backend.app.models.metric import Metric as MetricModel
from rhesis.backend.metrics.backends.base import MetricBackendStrategy
from rhesis.backend.metrics.backends.connector import (
    ConnectorBackendStrategy,
    ConnectorMetricSender,
)
from rhesis.backend.metrics.backends.local import LocalBackendStrategy
from rhesis.backend.metrics.metric_service import validate_metric_configs
from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
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

    Adding a new backend requires only a new :class:`MetricBackendStrategy`
    implementation and registering it – ``evaluate()`` is never modified.
    """

    def __init__(
        self,
        model: Optional[Any] = None,
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
        connector_metric_sender: Optional[ConnectorMetricSender] = None,
        extra_strategies: Optional[List[MetricBackendStrategy]] = None,
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

        self._local_strategy: MetricBackendStrategy = LocalBackendStrategy(
            model=model,
            db=db,
            organization_id=organization_id,
            score_evaluator=score_evaluator,
        )

        # Build the named strategy registry (backend_value -> strategy)
        self._strategies: Dict[str, MetricBackendStrategy] = {
            "sdk": ConnectorBackendStrategy(
                connector_metric_sender=connector_metric_sender,
                score_evaluator=score_evaluator,
            ),
        }

        if extra_strategies:
            for strategy in extra_strategies:
                self._strategies[strategy.backend_value()] = strategy

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
            max_workers: Maximum number of parallel workers for local backends.
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
        configs_by_backend: Dict[str, List[MetricConfig]] = {}
        for config in metric_configs:
            backend_val = getattr(config.backend, "value", config.backend)
            configs_by_backend.setdefault(backend_val, []).append(config)

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
