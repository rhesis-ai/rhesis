"""
Strategy protocol for metric evaluation.

Defines the interface that all metric strategies must implement,
allowing MetricEvaluator to dispatch to different strategies (local, sdk, etc.)
without being coupled to their concrete implementations.
"""

from typing import Any, Callable, Dict, List, Optional, Protocol

from rhesis.backend.metrics.inputs import EvaluationInputs
from rhesis.sdk.metrics import MetricConfig

OnMetricComplete = Optional[Callable[[str, Dict[str, Any]], None]]


class MetricStrategy(Protocol):
    """Strategy for evaluating metrics (local, sdk, etc.).

    Every strategy gets the same ``EvaluationInputs``; ``build_metric_evaluate_params``
    hands each metric only the inputs its signature names, so a strategy with no use for
    one (``ConnectorStrategy`` and ``instructions``, say) simply never reads it.

    Concrete implementations handle the specifics of each evaluation
    (parallel thread execution, RPC calls, remote APIs, etc.).  The evaluator
    only knows about this protocol and never imports the concrete classes.
    """

    def backend_value(self) -> str:
        """Backend identifier string (e.g. 'rhesis', 'deepeval', 'sdk')."""
        ...

    def evaluate(
        self,
        configs: List[MetricConfig],
        inputs: EvaluationInputs,
        *,
        max_workers: int = 5,
    ) -> Dict[str, Any]:
        """Evaluate all configs for this strategy."""
        ...

    async def a_evaluate(
        self,
        configs: List[MetricConfig],
        inputs: EvaluationInputs,
        *,
        on_metric_complete: OnMetricComplete = None,
    ) -> Dict[str, Any]:
        """Async version of evaluate using asyncio.gather instead of threads."""
        ...
