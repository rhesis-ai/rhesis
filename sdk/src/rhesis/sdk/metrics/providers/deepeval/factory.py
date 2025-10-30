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

    # Define which parameters each metric class accepts
    _supported_params = {
        # All DeepEval metrics support threshold and model
        "DeepEvalAnswerRelevancy": {"threshold", "model"},
        "DeepEvalBias": {"threshold", "model"},
        "DeepEvalFaithfulness": {"threshold", "model"},
        "DeepEvalContextualRelevancy": {"threshold", "model"},
        "DeepEvalContextualPrecision": {"threshold", "model"},
        "DeepEvalContextualRecall": {"threshold", "model"},
        "DeepEvalToxicity": {"threshold", "model"},
        "DeepEvalNonAdvice": {"threshold", "model", "advice_types"},
        "DeepEvalMisuse": {"threshold", "model", "domain"},
        "DeepEvalPIILeakage": {"threshold", "model"},
        "DeepEvalRoleViolation": {"threshold", "model", "role"},
        # DeepTeam metrics have custom parameters plus model
        "DeepTeamIllegal": {"illegal_category", "model"},
        "DeepTeamSafety": {"safety_category", "model"},
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
