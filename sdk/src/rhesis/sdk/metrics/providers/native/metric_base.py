from typing import Optional, Union

from rhesis.sdk.metrics.base import BaseMetric, MetricType
from rhesis.sdk.models.base import BaseLLM


class RhesisMetricBase(BaseMetric):
    """Base class for Rhesis' own metrics with common functionality."""

    def __init__(
        self,
        name: str,
        metric_type: MetricType = "rag",
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        super().__init__(name=name, metric_type=metric_type, model=model)

    def evaluate_score(self, *args, **kwargs) -> bool:
        """
        Evaluate if a score meets the success criteria based on score type and threshold operator.
        This method is implemented by the derived classes.
        """
        raise NotImplementedError("evaluate_score method is not implemented")
