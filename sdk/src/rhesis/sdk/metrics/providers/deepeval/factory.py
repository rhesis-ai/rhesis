from typing import List

from rhesis.sdk.metrics.base import BaseMetric, BaseMetricFactory
from rhesis.sdk.metrics.providers.deepeval.metrics import (
    DeepEvalAnswerRelevancy,
    DeepEvalContextualPrecision,
    DeepEvalContextualRecall,
    DeepEvalContextualRelevancy,
    DeepEvalFaithfulness,
    DeepEvalMisuse,
    DeepEvalNonAdvice,
    DeepEvalPIILeakage,
    DeepEvalRoleViolation,
    DeepEvalToxicity,
)


class DeepEvalMetricFactory(BaseMetricFactory):
    """Factory for creating DeepEval metric instances."""

    _metrics = {
        "DeepEvalAnswerRelevancy": DeepEvalAnswerRelevancy,
        "DeepEvalFaithfulness": DeepEvalFaithfulness,
        "DeepEvalContextualRelevancy": DeepEvalContextualRelevancy,
        "DeepEvalContextualPrecision": DeepEvalContextualPrecision,
        "DeepEvalContextualRecall": DeepEvalContextualRecall,
        "DeepEvalToxicity": DeepEvalToxicity,
        "DeepEvalNonAdvice": DeepEvalNonAdvice,
        "DeepEvalMisuse": DeepEvalMisuse,
        "DeepEvalPIILeakage": DeepEvalPIILeakage,
        "DeepEvalRoleViolation": DeepEvalRoleViolation,
    }

    # Define which parameters each metric class accepts
    _supported_params = {
        # All DeepEval metrics support threshold
        "DeepEvalAnswerRelevancy": {"threshold"},
        "DeepEvalFaithfulness": {"threshold"},
        "DeepEvalContextualRelevancy": {"threshold"},
        "DeepEvalContextualPrecision": {"threshold"},
        "DeepEvalContextualRecall": {"threshold"},
        "DeepEvalToxicity": {"threshold"},
        "DeepEvalNonAdvice": {"threshold"},
        "DeepEvalMisuse": {"threshold"},
        "DeepEvalPIILeakage": {"threshold"},
        "DeepEvalRoleViolation": {"threshold"},
    }

    def create(self, class_name: str, **kwargs) -> BaseMetric:
        """Create a metric instance using class name.

        Args:
            class_name: The class name to instantiate (e.g., 'DeepEvalContextualRecall')
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
