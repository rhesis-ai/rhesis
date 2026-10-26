"""Base class for DeepEval conversational metrics."""

import asyncio
import copy
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from deepeval.test_case import ConversationalTestCase
from deepeval.test_case import Turn as DeepEvalTurn

from rhesis.sdk.metrics.arguments import evaluation_arguments
from rhesis.sdk.metrics.base import MetricConfig, MetricResult
from rhesis.sdk.metrics.conversational.base import ConversationalMetricBase
from rhesis.sdk.metrics.conversational.types import ConversationHistory
from rhesis.sdk.metrics.expectations import ExpectationsLike
from rhesis.sdk.metrics.providers.deepeval.model import DeepEvalModelWrapper
from rhesis.sdk.metrics.utils import resilient_evaluation
from rhesis.sdk.models.base import BaseLLM

if TYPE_CHECKING:
    from rhesis.sdk.entities.trace import Trace


class DeepEvalConversationalBase(ConversationalMetricBase):
    """Base class for DeepEval conversational metrics with common functionality."""

    def __init__(
        self,
        config: MetricConfig,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
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
        """Convert standard message format to DeepEval format."""
        deepeval_turns = []
        for msg in conversation.messages:
            role, content, _ = ConversationHistory._msg_attrs(msg)
            if not content or role not in ("user", "assistant"):
                continue
            turn_kwargs: Dict[str, Any] = {"role": role, "content": content}
            if role == "assistant":
                tc = ConversationHistory._msg_tool_calls(msg)
                if tc:
                    turn_kwargs["tools_called"] = tc
            deepeval_turns.append(DeepEvalTurn(**turn_kwargs))  # type: ignore

        test_case_params: Dict[str, Any] = {"turns": deepeval_turns}
        if chatbot_role:
            test_case_params["chatbot_role"] = chatbot_role
        test_case_params.update(kwargs)

        return ConversationalTestCase(**test_case_params)

    # The assistant's role, for metrics that judge whether it kept to one.
    _chatbot_role: Optional[str] = None

    def _test_case(self, trace: "Trace") -> ConversationalTestCase:
        if self._metric is None:
            raise ValueError("DeepEval metric not initialized. Child class must set self._metric")
        conversation = trace.messages()
        if not conversation.messages:
            raise ValueError(f"{self.__class__.__name__} needs a conversation to evaluate.")
        return self._to_deepeval_format(conversation, chatbot_role=self._chatbot_role)

    @evaluation_arguments
    @resilient_evaluation
    def evaluate(
        self, trace: Optional["Trace"] = None, expectations: ExpectationsLike = None
    ) -> MetricResult:
        test_case = self._test_case(trace)
        self._metric.measure(test_case)

        return MetricResult(
            score=self._metric.score,
            details={
                "reason": getattr(self._metric, "reason", ""),
                "is_successful": self._metric.is_successful(),
                "threshold": getattr(self._metric, "threshold", None),
                "verdicts": getattr(self._metric, "verdicts", []),
                "window_size": getattr(self._metric, "window_size", None),
            },
        )

    @evaluation_arguments
    @resilient_evaluation
    async def a_evaluate(
        self, trace: Optional["Trace"] = None, expectations: ExpectationsLike = None
    ) -> MetricResult:
        """Async evaluate using DeepEval's a_measure if available, else to_thread.

        Uses a shallow copy of self._metric so concurrent evaluations don't
        clobber each other's mutable score/reason state.
        """
        test_case = self._test_case(trace)
        metric_copy = copy.copy(self._metric)

        if hasattr(metric_copy, "a_measure"):
            await metric_copy.a_measure(test_case)
        else:
            await asyncio.to_thread(metric_copy.measure, test_case)

        return MetricResult(
            score=metric_copy.score,
            details={
                "reason": getattr(metric_copy, "reason", ""),
                "is_successful": metric_copy.is_successful(),
                "threshold": getattr(metric_copy, "threshold", None),
                "verdicts": getattr(metric_copy, "verdicts", []),
                "window_size": getattr(metric_copy, "window_size", None),
            },
        )
