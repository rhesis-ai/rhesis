from typing import List

from rhesis.sdk.metrics.base import BaseMetric, BaseMetricFactory
from rhesis.sdk.metrics.providers.deepeval.metrics import (
    DeepEvalAnswerRelevancy,
    DeepEvalBias,
    DeepEvalContextualPrecision,
    DeepEvalContextualRecall,
    DeepEvalContextualRelevancy,
    DeepEvalFaithfulness,
    DeepEvalMisuse,
    DeepEvalNonAdvice,
    DeepEvalPIILeakage,
    DeepEvalRoleViolation,
    DeepEvalToxicity,
    DeepTeamIllegal,
    DeepTeamSafety,
)


class DeepEvalMetricFactory(BaseMetricFactory):
    """Factory for creating DeepEval metric instances."""

    _metrics = {
        "DeepEvalAnswerRelevancy": DeepEvalAnswerRelevancy,
        "DeepEvalBias": DeepEvalBias,
        "DeepEvalFaithfulness": DeepEvalFaithfulness,
        "DeepEvalContextualRelevancy": DeepEvalContextualRelevancy,
        "DeepEvalContextualPrecision": DeepEvalContextualPrecision,
        "DeepEvalContextualRecall": DeepEvalContextualRecall,
        "DeepEvalToxicity": DeepEvalToxicity,
        "DeepEvalNonAdvice": DeepEvalNonAdvice,
        "DeepEvalMisuse": DeepEvalMisuse,
        "DeepEvalPIILeakage": DeepEvalPIILeakage,
        "DeepEvalRoleViolation": DeepEvalRoleViolation,
        "DeepTeamIllegal": DeepTeamIllegal,
        "DeepTeamSafety": DeepTeamSafety,
    }

    # Common parameters supported by all metrics
    _common_params = {"model"}

    # Metric-specific parameters (in addition to common params)
    _supported_params = {
        # Most DeepEval metrics support threshold
        "DeepEvalAnswerRelevancy": {"threshold"},
        "DeepEvalBias": {"threshold"},
        "DeepEvalFaithfulness": {"threshold"},
        "DeepEvalContextualRelevancy": {"threshold"},
        "DeepEvalContextualPrecision": {"threshold"},
        "DeepEvalContextualRecall": {"threshold"},
        "DeepEvalToxicity": {"threshold"},
        "DeepEvalNonAdvice": {"threshold", "advice_types"},
        "DeepEvalMisuse": {"threshold", "domain"},
        "DeepEvalPIILeakage": {"threshold"},
        "DeepEvalRoleViolation": {"threshold", "role"},
        # DeepTeam metrics have custom parameters
        "DeepTeamIllegal": {"illegal_category"},
        "DeepTeamSafety": {"safety_category"},
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

        # Merge common params with metric-specific params
        metric_params = self._supported_params.get(class_name, set())
        supported_params = self._common_params | metric_params

        # Filter kwargs to only include supported parameters for this class
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported_params}

        return self._metrics[class_name](**filtered_kwargs)

    def list_supported_metrics(self) -> List[str]:
        """List available metric class names."""
        return list(self._metrics.keys())
