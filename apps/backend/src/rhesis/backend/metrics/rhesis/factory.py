from typing import List, Optional

from rhesis.backend.metrics.base import BaseMetricFactory, BaseMetric
from rhesis.backend.metrics.rhesis.metric_base import RhesisMetricBase
from rhesis.backend.metrics.rhesis.prompt_metric import RhesisPromptMetric, RhesisDetailedPromptMetric


class RhesisMetricFactory(BaseMetricFactory):
    """Factory for creating Rhesis' custom metric instances."""

    # Currently no metrics implemented, but will follow the same pattern
    _metrics = {
        # Add metrics as they're implemented, e.g.:
        # "RhesisCustomMetric": RhesisCustomMetric,
        "RhesisPromptMetric": RhesisPromptMetric,
        "RhesisDetailedPromptMetric": RhesisDetailedPromptMetric,
    }

    # Define which parameters each metric class accepts
    _supported_params = {
        # Example: "RhesisCustomMetric": {"threshold", "custom_param1", "custom_param2"},
        "RhesisPromptMetric": {
            "threshold", 
            "evaluation_prompt", 
            "evaluation_steps", 
            "reasoning", 
            "min_score", 
            "max_score", 
            "provider", 
            "model",
            "metric_type"
        },
        "RhesisDetailedPromptMetric": {
            "threshold", 
            "evaluation_prompt", 
            "evaluation_steps", 
            "reasoning", 
            "min_score", 
            "max_score", 
            "provider", 
            "model",
            "metric_type"
        },
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