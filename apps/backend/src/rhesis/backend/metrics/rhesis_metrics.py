from typing import List, Optional

from .base import BaseMetric, BaseMetricFactory, MetricResult, MetricType


class RhesisMetricBase(BaseMetric):
    """Base class for Rhesis' own metrics with common functionality."""

    def __init__(self, name: str, threshold: float = 0.5, metric_type: MetricType = "rag"):
        super().__init__(name=name, metric_type=metric_type)
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float):
        if not 0 <= value <= 1:
            raise ValueError("Threshold must be between 0 and 1")
        self._threshold = value


class RhesisMetricFactory(BaseMetricFactory):
    """Factory for creating Rhesis' custom metric instances."""

    # Currently no metrics implemented, but will follow the same pattern
    _metrics = {
        # Add metrics as they're implemented, e.g.:
        # "RhesisCustomMetric": RhesisCustomMetric,
    }

    # Define which parameters each metric class accepts
    _supported_params = {
        # Example: "RhesisCustomMetric": {"threshold", "custom_param1", "custom_param2"},
    }

    def create(self, class_name: str, **kwargs) -> BaseMetric:
        """Create a metric instance using class name.
        
        Args:
            class_name: The class name to instantiate (e.g., 'RhesisCustomMetric')
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

        # Filter kwargs to only include supported parameters for this class
        supported_params = self._supported_params.get(class_name, set())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported_params}
        
        return self._metrics[class_name](**filtered_kwargs)

    def list_supported_metrics(self) -> List[str]:
        """List available metric class names."""
        return list(self._metrics.keys())
