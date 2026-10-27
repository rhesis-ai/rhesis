"""Base class for conversational (multi-turn) metrics."""

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Union

from rhesis.sdk.metrics.base import MetricConfig, MetricResult, resolve_metric_model
from rhesis.sdk.metrics.expectations import ExpectationsLike
from rhesis.sdk.models.base import BaseLLM

if TYPE_CHECKING:
    from rhesis.sdk.entities.trace import Trace


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
            model: Language model for evaluation (BaseLLM instance or string identifier)
        """
        self.name = config.name
        self.description = config.description
        self.score_type = config.score_type
        self.metric_type = config.metric_type
        self.target = config.target
        self.requires_ground_truth = config.requires_ground_truth
        self.requires_context = config.requires_context
        self.class_name = config.class_name
        self.backend = config.backend
        self.id = config.id  # ID from backend when pulled

        self._model = self._set_model(model)

    def _set_model(self, model: Optional[Union[BaseLLM, str]]) -> BaseLLM:
        """Set the evaluation model."""
        return resolve_metric_model(model, self.name)

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
        trace: Optional["Trace"] = None,
        expectations: ExpectationsLike = None,
    ) -> MetricResult:
        """
        Evaluate a multi-turn conversation.

        Args:
            trace: The conversation's trace; ``trace.messages()`` reads it as messages.
            expectations: What the conversation should achieve (``goal``, ``instructions``).

        Implementations decorate this with ``evaluation_arguments``, so callers may pass
        ``conversation=`` (a ``ConversationHistory`` or a list of messages) instead of a trace.

        Returns:
            MetricResult with score and detailed evaluation
        """
        pass

    async def a_evaluate(
        self,
        trace: Optional["Trace"] = None,
        expectations: ExpectationsLike = None,
        **kwargs: Any,
    ) -> MetricResult:
        """
        Async version of evaluate with a default to_thread fallback.

        Subclasses with native async implementations should override this.
        """
        return await asyncio.to_thread(self.evaluate, trace, expectations, **kwargs)
