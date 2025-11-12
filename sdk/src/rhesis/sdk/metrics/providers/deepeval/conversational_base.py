"""Base class for DeepEval conversational metrics."""

from typing import Any, Dict, Optional, Union

from deepeval.test_case import ConversationalTestCase
from deepeval.test_case import Turn as DeepEvalTurn

from rhesis.sdk.metrics.base import MetricConfig, MetricResult
from rhesis.sdk.metrics.conversational.base import ConversationalMetricBase
from rhesis.sdk.metrics.conversational.types import ConversationHistory
from rhesis.sdk.metrics.providers.deepeval.model import DeepEvalModelWrapper
from rhesis.sdk.models.base import BaseLLM


class DeepEvalConversationalBase(ConversationalMetricBase):
    """Base class for DeepEval conversational metrics with common functionality."""

    def __init__(
        self,
        config: MetricConfig,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        """
        Initialize DeepEval conversational metric.

        Args:
            config: Metric configuration
            model: LLM model for evaluation
        """
        super().__init__(config=config, model=model)
        self._deepeval_model = DeepEvalModelWrapper(self._model)
        self._metric = None  # Will be set by child classes

    @property
    def deepeval_model(self):
        """Get the DeepEval model wrapper."""
        return self._deepeval_model

    def _update_model(self):
        """Update DeepEval model wrapper when model changes."""
        self._deepeval_model = DeepEvalModelWrapper(self._model)
        if self._metric:
            self._metric.model = self._deepeval_model

    @property
    def model(self) -> BaseLLM:
        """Get the current model."""
        return self._model

    @model.setter
    def model(self, value: Union[BaseLLM, str]):
        """Set the model and update DeepEval wrapper."""
        self._model = self._set_model(value)
        self._update_model()

    def _to_deepeval_format(
        self, conversation: ConversationHistory, chatbot_role: Optional[str] = None, **kwargs: Any
    ) -> ConversationalTestCase:
        """
        Convert standard message format to DeepEval format.

        DeepEval only needs role + content, so we extract those.

        Args:
            conversation: Conversation in standard format
            chatbot_role: Optional role for the chatbot
            **kwargs: Additional parameters for ConversationalTestCase

        Returns:
            DeepEval ConversationalTestCase
        """
        simple_turns = conversation.get_simple_turns()

        deepeval_turns = []
        for turn in simple_turns:
            role = turn["role"]
            content = turn["content"]
            # DeepEval Turn expects role to be "user" or "assistant" only
            # Skip tool and system messages
            if role not in ("user", "assistant"):
                continue
            deepeval_turns.append(DeepEvalTurn(role=role, content=content))  # type: ignore

        # Build test case parameters
        test_case_params = {"turns": deepeval_turns}
        if chatbot_role:
            test_case_params["chatbot_role"] = chatbot_role

        # Add any additional kwargs
        test_case_params.update(kwargs)

        return ConversationalTestCase(**test_case_params)

    def evaluate(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
        instructions: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        chatbot_role: Optional[str] = None,
        **kwargs: Any,
    ) -> MetricResult:
        """
        Evaluate conversation using DeepEval metric.

        Args:
            conversation_history: Conversation to evaluate
            goal: Optional goal (used by some metrics)
            instructions: Optional instructions (used by some metrics)
            context: Optional context (used by some metrics)
            chatbot_role: Optional chatbot role (required for Role Adherence)
            **kwargs: Additional parameters

        Returns:
            MetricResult with DeepEval evaluation
        """
        if self._metric is None:
            raise ValueError("DeepEval metric not initialized. Child class must set self._metric")

        # Convert to DeepEval format, passing chatbot_role if provided
        test_case = self._to_deepeval_format(
            conversation_history, chatbot_role=chatbot_role, **kwargs
        )

        # Run DeepEval's measure method
        self._metric.measure(test_case)

        # Extract results
        return MetricResult(
            score=self._metric.score,
            details={
                "reason": getattr(self._metric, "reason", ""),
                "is_successful": self._metric.is_successful(),
                "threshold": getattr(self._metric, "threshold", None),
                # DeepEval-specific details
                "verdicts": getattr(self._metric, "verdicts", []),
                "window_size": getattr(self._metric, "window_size", None),
            },
        )
