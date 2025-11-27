"""DeepEval conversational metric implementations."""

from typing import Any, Dict, List, Optional, Union

from rhesis.sdk.metrics.base import MetricConfig, MetricResult, MetricType, ScoreType
from rhesis.sdk.metrics.conversational.types import ConversationHistory
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

        from deepeval.metrics import TurnRelevancyMetric  # type: ignore

        # Initialize DeepEval metric
        self._metric = TurnRelevancyMetric(
            threshold=threshold,
            window_size=window_size,
            model=self._deepeval_model,
        )

        self.threshold = threshold
        self.window_size = window_size


class DeepEvalRoleAdherence(DeepEvalConversationalBase):
    """
    DeepEval Role Adherence metric.

    Evaluates whether the assistant maintains its assigned role throughout
    the conversation. The role is inferred from the conversation context.

    Example:
        >>> from rhesis.sdk.metrics import DeepEvalRoleAdherence, ConversationHistory
        >>>
        >>> metric = DeepEvalRoleAdherence(threshold=0.7)
        >>>
        >>> conversation = ConversationHistory.from_messages([
        ...     {"role": "user", "content": "I need help with my order."},
        ...     {"role": "assistant", "content": "I'll help you with that right away."},
        ...     {"role": "user", "content": "Can you also give me stock tips?"},
        ...     {
        ...         "role": "assistant",
        ...         "content": "I'm a support agent, I can only help with orders."
        ...     },
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
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        """
        Initialize Role Adherence metric.

        Args:
            threshold: Minimum passing score (0.0 to 1.0)
            model: LLM model for evaluation
        """
        config = MetricConfig(
            name="role_adherence",
            description="Evaluates whether assistant maintains its assigned role",
            score_type=ScoreType.NUMERIC,
            metric_type=MetricType.CONVERSATIONAL,
            requires_ground_truth=False,
            requires_context=False,
        )

        super().__init__(config=config, model=model)

        from deepeval.metrics import RoleAdherenceMetric  # type: ignore

        # Initialize DeepEval metric (role is inferred from conversation)
        self._metric = RoleAdherenceMetric(
            threshold=threshold,
            model=self._deepeval_model,
        )

        self.threshold = threshold

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
        Evaluate conversation for role adherence.

        Args:
            conversation_history: Conversation to evaluate
            goal: Optional goal (not used by this metric)
            instructions: Optional instructions (not used by this metric)
            context: Optional context (not used by this metric)
            chatbot_role: Optional chatbot role. If not provided, defaults to "assistant"
            **kwargs: Additional parameters

        Returns:
            MetricResult with role adherence evaluation
        """
        # If chatbot_role is not provided, use a default
        if chatbot_role is None:
            chatbot_role = "assistant"

        # Call parent evaluate with chatbot_role
        return super().evaluate(
            conversation_history=conversation_history,
            goal=goal,
            instructions=instructions,
            context=context,
            chatbot_role=chatbot_role,
            **kwargs,
        )


class DeepEvalKnowledgeRetention(DeepEvalConversationalBase):
    """
    DeepEval Knowledge Retention metric.

    Evaluates the assistant's ability to retain and recall factual information
    that was introduced earlier in the conversation. Measures whether the
    assistant can reference and build upon knowledge shared in previous turns.

    Example:
        >>> from rhesis.sdk.metrics import DeepEvalKnowledgeRetention, ConversationHistory
        >>>
        >>> metric = DeepEvalKnowledgeRetention(threshold=0.7)
        >>>
        >>> conversation = ConversationHistory.from_messages([
        ...     {"role": "user", "content": "My order number is ABC123."},
        ...     {"role": "assistant", "content": "I've noted your order number ABC123."},
        ...     {"role": "user", "content": "What was my order number again?"},
        ...     {"role": "assistant", "content": "Your order number is ABC123."},
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
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        """
        Initialize Knowledge Retention metric.

        Args:
            threshold: Minimum passing score (0.0 to 1.0)
            model: LLM model for evaluation
        """
        config = MetricConfig(
            name="knowledge_retention",
            description="Evaluates assistant's ability to retain conversation facts",
            score_type=ScoreType.NUMERIC,
            metric_type=MetricType.CONVERSATIONAL,
            requires_ground_truth=False,
            requires_context=False,
        )

        super().__init__(config=config, model=model)

        from deepeval.metrics import KnowledgeRetentionMetric  # type: ignore

        # Initialize DeepEval metric
        self._metric = KnowledgeRetentionMetric(
            threshold=threshold,
            model=self._deepeval_model,
        )

        self.threshold = threshold


class DeepEvalConversationCompleteness(DeepEvalConversationalBase):
    """
    DeepEval Conversation Completeness metric.

    Evaluates whether the conversation reaches a satisfactory conclusion where
    the user's needs are met. Assesses if the assistant successfully addresses
    all aspects of the user's request and brings the conversation to completion.

    Example:
        >>> from rhesis.sdk.metrics import DeepEvalConversationCompleteness, ConversationHistory
        >>>
        >>> metric = DeepEvalConversationCompleteness(threshold=0.7, window_size=3)
        >>>
        >>> conversation = ConversationHistory.from_messages([
        ...     {"role": "user", "content": "I need to cancel my subscription."},
        ...     {"role": "assistant", "content": "I can help with that."},
        ...     {"role": "user", "content": "Thank you!"},
        ...     {"role": "assistant", "content": "Your subscription has been cancelled."},
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
        window_size: int = 3,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        """
        Initialize Conversation Completeness metric.

        Args:
            threshold: Minimum passing score (0.0 to 1.0)
            window_size: Number of recent turns to consider (default: 3)
            model: LLM model for evaluation
        """
        config = MetricConfig(
            name="conversation_completeness",
            description="Evaluates whether conversation reaches satisfactory completion",
            score_type=ScoreType.NUMERIC,
            metric_type=MetricType.CONVERSATIONAL,
            requires_ground_truth=False,
            requires_context=False,
        )

        super().__init__(config=config, model=model)

        from deepeval.metrics import ConversationCompletenessMetric  # type: ignore

        # Initialize DeepEval metric
        self._metric = ConversationCompletenessMetric(
            threshold=threshold,
            window_size=window_size,
            model=self._deepeval_model,
        )

        self.threshold = threshold
        self.window_size = window_size


class DeepEvalGoalAccuracy(DeepEvalConversationalBase):
    """
    DeepEval Goal Accuracy metric.

    Evaluates the assistant's ability to plan and execute tasks to achieve
    specific goals. Measures whether the assistant takes appropriate steps
    and makes correct decisions to accomplish the stated objective.

    Example:
        >>> from rhesis.sdk.metrics import DeepEvalGoalAccuracy, ConversationHistory
        >>>
        >>> metric = DeepEvalGoalAccuracy(threshold=0.7)
        >>>
        >>> conversation = ConversationHistory.from_messages([
        ...     {"role": "user", "content": "Book me a flight to Paris for next week."},
        ...     {"role": "assistant", "content": "I'll search for flights to Paris."},
        ...     {"role": "assistant", "content": "Found flights. Shall I book?"},
        ...     {"role": "user", "content": "Yes, please."},
        ...     {"role": "assistant", "content": "Flight booked successfully."},
        ... ])
        >>>
        >>> result = metric.evaluate(
        ...     conversation_history=conversation,
        ...     goal="Book a flight to Paris"
        ... )
        >>> print(f"Score: {result.score}")
        >>> print(f"Successful: {result.details['is_successful']}")
    """

    metric_type = MetricType.CONVERSATIONAL

    def __init__(
        self,
        threshold: float = 0.5,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        """
        Initialize Goal Accuracy metric.

        Args:
            threshold: Minimum passing score (0.0 to 1.0)
            model: LLM model for evaluation
        """
        config = MetricConfig(
            name="goal_accuracy",
            description="Evaluates assistant's ability to achieve conversation goals",
            score_type=ScoreType.NUMERIC,
            metric_type=MetricType.CONVERSATIONAL,
            requires_ground_truth=False,
            requires_context=False,
        )

        super().__init__(config=config, model=model)

        from deepeval.metrics import GoalAccuracyMetric  # type: ignore

        # Initialize DeepEval metric
        self._metric = GoalAccuracyMetric(
            threshold=threshold,
            model=self._deepeval_model,
        )

        self.threshold = threshold


class DeepEvalToolUse(DeepEvalConversationalBase):
    """
    DeepEval Tool Use metric.

    Evaluates the assistant's capability in selecting and utilizing tools
    appropriately during conversations. Measures whether the assistant makes
    correct decisions about when to use tools, which tools to use, and how
    to use them effectively.

    Example:
        >>> from rhesis.sdk.metrics import DeepEvalToolUse, ConversationHistory
        >>>
        >>> available_tools = [
        ...     {"name": "get_weather", "description": "Get current weather"}
        ... ]
        >>> metric = DeepEvalToolUse(available_tools=available_tools, threshold=0.7)
        >>>
        >>> conversation = ConversationHistory.from_messages([
        ...     {"role": "user", "content": "What's the weather like?"},
        ...     {
        ...         "role": "assistant",
        ...         "content": "",
        ...         "tool_calls": [{"id": "1", "function": {"name": "get_weather"}}]
        ...     },
        ...     {"role": "tool", "tool_call_id": "1", "name": "get_weather", "content": "Sunny"},
        ...     {"role": "assistant", "content": "It's sunny today!"},
        ... ])
        >>>
        >>> result = metric.evaluate(conversation_history=conversation)
        >>> print(f"Score: {result.score}")
        >>> print(f"Successful: {result.details['is_successful']}")
    """

    metric_type = MetricType.CONVERSATIONAL

    def __init__(
        self,
        available_tools: Optional[List[Dict[str, Any]]] = None,
        threshold: float = 0.5,
        model: Optional[Union[BaseLLM, str]] = None,
    ):
        """
        Initialize Tool Use metric.

        Args:
            available_tools: Optional list of available tools (each with 'name' and
                           optional 'description'). Defaults to empty list if not provided.
            threshold: Minimum passing score (0.0 to 1.0)
            model: LLM model for evaluation
        """
        if available_tools is None:
            available_tools = []
        config = MetricConfig(
            name="tool_use",
            description="Evaluates assistant's tool selection and usage",
            score_type=ScoreType.NUMERIC,
            metric_type=MetricType.CONVERSATIONAL,
            requires_ground_truth=False,
            requires_context=False,
        )

        super().__init__(config=config, model=model)

        from deepeval.metrics import ToolUseMetric  # type: ignore

        # Initialize DeepEval metric
        self._metric = ToolUseMetric(
            available_tools=available_tools,
            threshold=threshold,
            model=self._deepeval_model,
        )

        self.available_tools = available_tools
        self.threshold = threshold
