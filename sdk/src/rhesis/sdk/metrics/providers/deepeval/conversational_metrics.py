"""DeepEval conversational metric implementations."""

from typing import Optional, Union

from deepeval.metrics import TurnRelevancyMetric

from rhesis.sdk.metrics.base import MetricConfig, MetricType, ScoreType
from rhesis.sdk.metrics.providers.deepeval.conversational_base import (
    DeepEvalConversationalBase,
)
from rhesis.sdk.models.base import BaseLLM


class DeepEvalTurnRelevancy(DeepEvalConversationalBase):
    """
    DeepEval Turn Relevancy metric.

    Evaluates whether assistant responses are relevant to the conversational
    context throughout a conversation.

    The metric uses a sliding window approach to evaluate each assistant turn
    against its conversational context.

    Example:
        >>> from rhesis.sdk.metrics import DeepEvalTurnRelevancy, ConversationHistory
        >>>
        >>> metric = DeepEvalTurnRelevancy(threshold=0.5, window_size=10)
        >>>
        >>> conversation = ConversationHistory.from_messages([
        ...     {"role": "user", "content": "What insurance do you offer?"},
        ...     {"role": "assistant", "content": "We offer auto, home, and life."},
        ...     {"role": "user", "content": "Tell me about auto coverage."},
        ...     {"role": "assistant", "content": "Auto includes liability and collision."},
        ... ])
        >>>
        >>> result = metric.evaluate(conversation_history=conversation)
        >>> print(f"Score: {result.score}")
        >>> print(f"Successful: {result.details['is_successful']}")
    """

    metric_type = MetricType.CONVERSATIONAL

    def __init__(
        self,
        threshold: float = 0.5,
        window_size: int = 10,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        """
        Initialize Turn Relevancy metric.

        Args:
            threshold: Minimum passing score (0.0 to 1.0)
            window_size: Size of sliding window for context evaluation
            model: LLM model for evaluation
        """
        config = MetricConfig(
            name="turn_relevancy",
            description="Evaluates relevance of assistant responses in conversation",
            score_type=ScoreType.NUMERIC,
            metric_type=MetricType.CONVERSATIONAL,
            requires_ground_truth=False,
            requires_context=False,
        )

        super().__init__(config=config, model=model)

        # Initialize DeepEval metric
        self._metric = TurnRelevancyMetric(
            threshold=threshold,
            window_size=window_size,
            model=self._deepeval_model,
        )

        self.threshold = threshold
        self.window_size = window_size
