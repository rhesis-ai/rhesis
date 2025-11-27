import logging
from typing import List

from rhesis.sdk.metrics.base import BaseMetric, BaseMetricFactory
from rhesis.sdk.metrics.providers.deepeval.conversational_metrics import (
    DeepEvalConversationCompleteness,
    DeepEvalGoalAccuracy,
    DeepEvalKnowledgeRetention,
    DeepEvalRoleAdherence,
    DeepEvalToolUse,
    DeepEvalTurnRelevancy,
)
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

logger = logging.getLogger(__name__)


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
        # Conversational metrics
        "DeepEvalTurnRelevancy": DeepEvalTurnRelevancy,
        "DeepEvalRoleAdherence": DeepEvalRoleAdherence,
        "DeepEvalKnowledgeRetention": DeepEvalKnowledgeRetention,
        "DeepEvalConversationCompleteness": DeepEvalConversationCompleteness,
        "DeepEvalGoalAccuracy": DeepEvalGoalAccuracy,
        "DeepEvalToolUse": DeepEvalToolUse,
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
        # Conversational metrics
        "DeepEvalTurnRelevancy": {"threshold", "window_size"},
        "DeepEvalRoleAdherence": {"threshold"},
        "DeepEvalKnowledgeRetention": {"threshold"},
        "DeepEvalConversationCompleteness": {"threshold", "window_size"},
        "DeepEvalGoalAccuracy": {"threshold"},
        "DeepEvalToolUse": {"threshold", "available_tools"},
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

        # Extract parameters from the 'parameters' dictionary if present
        parameters = (
            kwargs.pop("parameters", {}) if isinstance(kwargs.get("parameters"), dict) else {}
        )

        # Combine parameters with kwargs, with kwargs taking precedence
        combined_kwargs = {**parameters, **kwargs}

        # Merge common params with metric-specific params
        metric_params = self._supported_params.get(class_name, set())
        supported_params = self._common_params | metric_params

        # Filter kwargs to only include supported parameters for this class
        filtered_kwargs = {k: v for k, v in combined_kwargs.items() if k in supported_params}

        try:
            return self._metrics[class_name](**filtered_kwargs)
        except Exception as e:
            logger.error(
                f"Failed to create DeepEval metric '{class_name}': {e}. "
                f"This may be due to missing deepeval configuration or dependencies. "
                f"Ensure deepeval is properly installed and configured."
            )
            raise RuntimeError(
                f"Failed to instantiate DeepEval metric '{class_name}'. Error: {e}"
            ) from e

    def list_supported_metrics(self) -> List[str]:
        """List available metric class names."""
        return list(self._metrics.keys())
