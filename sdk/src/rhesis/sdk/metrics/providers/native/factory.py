from typing import List

from rhesis.sdk.metrics.base import BaseMetric, BaseMetricFactory
from rhesis.sdk.metrics.providers.native.categorical_judge import (
    CategoricalJudge,
)
from rhesis.sdk.metrics.providers.native.numeric_judge import NumericJudge


class RhesisMetricFactory(BaseMetricFactory):
    """Factory for creating Rhesis' custom metric instances."""

    # Currently no metrics implemented, but will follow the same pattern
    _metrics = {
        # Add metrics as they're implemented, e.g.:
        # "RhesisCustomMetric": RhesisCustomMetric,
        "CategoricalJudge": CategoricalJudge,
        "NumericJudge": NumericJudge,
    }

    # Common parameters supported by all metrics
    _common_params = {"model"}

    # Metric-specific parameters (in addition to common params)
    _supported_params = {
        # Example: "RhesisCustomMetric": {"threshold", "custom_param1", "custom_param2"},
        "CategoricalJudge": {
            "categories",
            "passing_categories",
            "evaluation_prompt",
            "evaluation_steps",
            "reasoning",
            "evaluation_examples",
            "name",
            "description",
            "requires_ground_truth",
            "requires_context",
            "metric_type",
        },
        "NumericJudge": {
            "threshold",
            "reference_score",
            "threshold_operator",
            "score_type",
            "evaluation_prompt",
            "evaluation_steps",
            "reasoning",
            "evaluation_examples",
            "min_score",
            "max_score",
            "provider",
            "api_key",
            "metric_type",
            "name",
            "description",
        },
    }

    # Define required parameters for each metric class
    _required_params = {
        "CategoricalJudge": {"categories", "passing_categories"},
        "NumericJudge": {"evaluation_prompt"},
    }

    def create(self, class_name: str, **kwargs) -> BaseMetric:
        """Create a metric instance using class name.

        Args:
            class_name: The class name to instantiate (e.g., 'NumericJudge')
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

        # Extract parameters from the 'parameters' dictionary if present
        parameters = (
            kwargs.pop("parameters", {}) if isinstance(kwargs.get("parameters"), dict) else {}
        )

        # Combine parameters with kwargs, with kwargs taking precedence
        combined_kwargs = {**parameters, **kwargs}

        # Set the name parameter if not present
        if "name" not in combined_kwargs and class_name in self._metrics:
            # Use class name as a fallback for the name
            combined_kwargs["name"] = class_name.lower()

        # Check for required parameters
        required_params = self._required_params.get(class_name, set())
        missing_params = required_params - set(combined_kwargs.keys())
        if missing_params:
            raise ValueError(
                f"Missing required parameters for {class_name}: {missing_params}. "
                f"Provided parameters: {set(combined_kwargs.keys())}"
            )

        # Merge common params with metric-specific params
        metric_params = self._supported_params.get(class_name, set())
        supported_params = self._common_params | metric_params

        # Filter kwargs to only include supported parameters for this class
        filtered_kwargs = {k: v for k, v in combined_kwargs.items() if k in supported_params}

        return self._metrics[class_name](**filtered_kwargs)

    def list_supported_metrics(self) -> List[str]:
        """List available metric class names."""
        return list(self._metrics.keys())
