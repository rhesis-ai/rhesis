from typing import List

from rhesis.sdk.metrics.base import BaseMetric, BaseMetricFactory
from rhesis.sdk.metrics.providers.ragas.metrics import (
    RagasAnswerAccuracy,
    RagasAspectCritic,
    RagasContextRelevance,
    RagasFaithfulness,
)


class RagasMetricFactory(BaseMetricFactory):
    """Factory for creating Ragas metric instances."""

    _metrics = {
        "RagasAnswerAccuracy": RagasAnswerAccuracy,
        "RagasContextRelevance": RagasContextRelevance,
        "RagasFaithfulness": RagasFaithfulness,
        "RagasAspectCritic": RagasAspectCritic,
    }

    # Common parameters supported by all metrics
    _common_params = {"model"}

    # Metric-specific parameters (in addition to common params)
    _supported_params = {
        "RagasAnswerAccuracy": {"threshold"},
        "RagasContextRelevance": {"threshold"},
        "RagasFaithfulness": {"threshold"},
        "RagasAspectCritic": {"threshold", "name", "definition"},
    }

    def create(self, class_name: str, **kwargs) -> BaseMetric:
        """Create a metric instance using class name.

        Args:
            class_name: The class name to instantiate (e.g., 'RagasContextualPrecision')
            **kwargs: Additional parameters to pass to the class constructor

        Returns:
            BaseMetric: An instance of the specified metric class

        Raises:
            ValueError: If the specified class doesn't exist in this module
        """
        if class_name not in self._metrics:
            available_classes = list(self._metrics.keys())
            raise ValueError(
                f"Unknown metric class: {class_name}. Available classes: {available_classes}"
            )

        # Merge common params with metric-specific params
        metric_params = self._supported_params.get(class_name, set())
        supported_params = self._common_params | metric_params

        # Filter kwargs to only include supported parameters for this class
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported_params}

        return self._metrics[class_name](**filtered_kwargs)

    def list_supported_metrics(self) -> List[str]:
        """List available metric class names."""
        return list(self._metrics.keys())
