"""Base class for conversational (multi-turn) metrics."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

from rhesis.sdk.metrics.base import MetricConfig, MetricResult
from rhesis.sdk.metrics.conversational.types import ConversationHistory
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model


class ConversationalMetricBase(ABC):
    """
    Base class for all conversational (multi-turn) evaluation metrics.

    Conversational metrics evaluate entire conversations against specific criteria
    such as goal achievement, context retention, or conversation quality.

    They are framework-agnostic and can be used with any conversation system
    (Penelope, LangChain, CrewAI, custom chatbots, etc.).
    """

    def __init__(self, config: MetricConfig, model: Optional[Union[BaseLLM, str]] = None):
        """
        Initialize conversational metric.

        Args:
            config: Metric configuration
            model: LLM model for evaluation (BaseLLM instance or string identifier)
        """
        self.name = config.name
        self.description = config.description
        self.score_type = config.score_type
        self.metric_type = config.metric_type
        self.metric_scope = config.metric_scope
        self.requires_ground_truth = config.requires_ground_truth
        self.requires_context = config.requires_context
        self.class_name = config.class_name
        self.backend = config.backend

        self._model = self._set_model(model)

    def _set_model(self, model: Optional[Union[BaseLLM, str]]) -> BaseLLM:
        """Set the evaluation model."""
        if isinstance(model, BaseLLM):
            return model
        return get_model(model)

    @property
    def model(self) -> BaseLLM:
        """Get the current model."""
        return self._model

    @model.setter
    def model(self, value: Union[BaseLLM, str]):
        """Set the model."""
        self._model = self._set_model(value)

    @property
    def is_goal_achievement_metric(self) -> bool:
        """
        Identify whether this metric is a goal achievement metric.

        Goal achievement metrics provide detailed criteria evaluations and
        may need special handling to avoid data duplication in systems
        that maintain separate detailed goal evaluation data.

        Returns:
            False by default. Subclasses like GoalAchievementJudge override this.
        """
        return False

    @abstractmethod
    def evaluate(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
        instructions: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> MetricResult:
        """
        Evaluate a multi-turn conversation.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional goal or success criteria
            instructions: Optional instructions that guided the conversation
            context: Optional additional context
            **kwargs: Additional metric-specific parameters

        Returns:
            MetricResult with score and detailed evaluation
        """
        pass
