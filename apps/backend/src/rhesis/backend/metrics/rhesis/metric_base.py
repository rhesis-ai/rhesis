from typing import List, Optional

from rhesis.backend.metrics.base import BaseMetric, MetricResult, MetricType


class RhesisMetricBase(BaseMetric):
    """Base class for Rhesis' own metrics with common functionality."""

    def __init__(self, name: str, threshold: float = 0.5, metric_type: MetricType = "rag"):
        super().__init__(name=name, metric_type=metric_type)
        self._threshold = threshold  # Store directly without validation

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float):
        # No range validation - let the derived classes handle threshold validation if needed
        self._threshold = value 