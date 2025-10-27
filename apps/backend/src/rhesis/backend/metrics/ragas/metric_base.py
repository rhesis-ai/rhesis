from rhesis.backend.metrics.base import BaseMetric, MetricType


class RagasMetricBase(BaseMetric):
    """Base class for Ragas metrics with common functionality."""

    def __init__(self, name: str, threshold: float = 0.5, metric_type: MetricType = "rag"):
        super().__init__(name=name, metric_type=metric_type)
        self.threshold = threshold  # Use the setter for validation
        # Actual Ragas implementation to be added

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float):
        if not 0 <= value <= 1:
            raise ValueError("Threshold must be between 0 and 1")
        self._threshold = value
