"""
Strategy protocol for metric evaluation.

Defines the interface that all metric strategies must implement,
allowing MetricEvaluator to dispatch to different strategies (local, sdk, etc.)
without being coupled to their concrete implementations.
"""

from typing import Any, Dict, List, Protocol

from rhesis.sdk.metrics import MetricConfig


class MetricStrategy(Protocol):
    """Strategy for evaluating metrics (local, sdk, etc.).

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
        input_text: str,
        output_text: str,
        expected_output: str,
        context: List[str],
        *,
        max_workers: int = 5,
        conversation_history: Any = None,
        metadata: Dict[str, Any] | None = None,
        tool_calls: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Evaluate all configs for this strategy.

        Args:
            configs: Metric configurations assigned to this strategy.
            input_text: The input query or question.
            output_text: The actual LLM output.
            expected_output: The expected or reference output.
            context: List of context strings used for the response.
            max_workers: Maximum parallel workers (used by local strategy).
            conversation_history: Optional conversation history.
            metadata: Optional metadata dict.
            tool_calls: Optional list of tool calls made by the endpoint.

        Returns:
            Dict keyed by metric name containing result dicts.
        """
        ...
