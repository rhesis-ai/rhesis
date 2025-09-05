from typing import List, Optional

from rhesis.sdk.metrics.base import MetricResult, retry_evaluation
from rhesis.sdk.metrics.providers.ragas.metric_base import RagasMetricBase


class RagasAnswerRelevancy(RagasMetricBase):
    """Ragas implementation of Answer Relevancy metric."""

    def __init__(self, threshold: float = 0.5):
        super().__init__(name="answer_relevancy", threshold=threshold, metric_type="rag")
        # Initialize Ragas specific implementation

    @retry_evaluation()
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        # Implement Ragas specific evaluation logic
        # Placeholder implementation
        return MetricResult(
            score=0.0,
            details={
                "reason": "Not implemented yet",
                "is_successful": False,
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return True


class RagasContextualPrecision(RagasMetricBase):
    """Ragas implementation of Contextual Precision metric."""

    def __init__(self, threshold: float = 0.5):
        super().__init__(name="contextual_precision", threshold=threshold, metric_type="rag")
        # Initialize Ragas specific implementation

    @retry_evaluation()
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        # Implement Ragas specific evaluation logic
        # Placeholder implementation
        return MetricResult(
            score=0.0,
            details={
                "reason": "Not implemented yet",
                "is_successful": False,
                "threshold": self._threshold,
            },
        )

    @property
    def requires_ground_truth(self) -> bool:
        return False
