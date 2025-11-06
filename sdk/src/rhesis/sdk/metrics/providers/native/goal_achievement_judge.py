"""Goal Achievement Judge for evaluating conversation goal completion."""

from dataclasses import dataclass, fields
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field

from rhesis.sdk.metrics.base import MetricResult, MetricType, ScoreType
from rhesis.sdk.metrics.constants import OPERATOR_MAP, ThresholdOperator
from rhesis.sdk.metrics.conversational.types import ConversationHistory
from rhesis.sdk.metrics.providers.native.conversational_judge import (
    ConversationalJudge,
    ConversationalJudgeConfig,
)
from rhesis.sdk.models import BaseLLM

SCORE_TYPE = ScoreType.NUMERIC


@dataclass
class GoalAchievementJudgeConfig(ConversationalJudgeConfig):
    """Configuration for Goal Achievement Judge."""

    min_score: Optional[float] = None
    max_score: Optional[float] = None
    threshold: Optional[float] = None
    threshold_operator: Union[ThresholdOperator, str] = ThresholdOperator.GREATER_THAN_OR_EQUAL

    def __post_init__(self):
        # Convert string to enum if needed
        if isinstance(self.threshold_operator, str):
            self.threshold_operator = ThresholdOperator(self.threshold_operator)
        self._validate_score_range(self.min_score, self.max_score)
        self._set_score_parameters(self.min_score, self.max_score, self.threshold)
        super().__post_init__()

    def _validate_score_range(self, min_score: Optional[float], max_score: Optional[float]) -> None:
        """Validate that min_score and max_score are provided together."""
        if min_score is not None and max_score is None:
            raise ValueError("Only min_score was set, please set max_score")

        if min_score is None and max_score is not None:
            raise ValueError("Only max_score was set, please set min_score")

        if min_score is not None and max_score is not None and min_score == max_score:
            raise ValueError("min_score and max_score cannot be the same")

        if min_score is not None and max_score is not None and min_score > max_score:
            raise ValueError("min_score cannot be greater than max_score")

    def _set_score_parameters(
        self, min_score: Optional[float], max_score: Optional[float], threshold: Optional[float]
    ) -> None:
        """Set up score parameters with validation."""
        # For numeric scores, we need min_score, max_score, and threshold
        self.min_score = min_score if min_score is not None else 0
        self.max_score = max_score if max_score is not None else 1

        if threshold is None:
            self.threshold = self.min_score + (self.max_score - self.min_score) / 2
        else:
            self.threshold = threshold

        if not (self.min_score <= self.threshold <= self.max_score):
            raise ValueError(f"Threshold must be between {self.min_score} and {self.max_score}")


class GoalAchievementScoreResponse(BaseModel):
    """Model for structured response from LLM evaluation."""

    score: float = Field(description="Goal achievement score")
    reason: str = Field(description="Explanation for the score", default="")


class GoalAchievementJudge(ConversationalJudge):
    """
    Native conversational metric that evaluates goal achievement in conversations.

    This judge evaluates whether a conversation successfully achieves its stated goal,
    providing a numeric score based on how well the assistant helped the user reach
    their objective.

    The default prompt template includes built-in goal achievement criteria that are
    used when custom prompts are not provided. These defaults can be overridden by
    passing custom values for evaluation_prompt, evaluation_steps, or reasoning.
    """

    def __init__(
        self,
        evaluation_prompt: Optional[str] = None,
        evaluation_steps: Optional[str] = None,
        reasoning: Optional[str] = None,
        evaluation_examples: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        threshold: Optional[float] = None,
        threshold_operator: Union[ThresholdOperator, str] = ThresholdOperator.GREATER_THAN_OR_EQUAL,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metric_type: Optional[Union[str, MetricType]] = None,
        model: Optional[Union[str, BaseLLM]] = None,
        **kwargs,
    ):
        """
        Initialize the Goal Achievement Judge.

        Args:
            evaluation_prompt: The main evaluation criteria. If None, uses template defaults
                for goal achievement evaluation.
            evaluation_steps: Step-by-step evaluation process. If None, uses template defaults.
            reasoning: Guidelines for reasoning. If None, uses template defaults.
            evaluation_examples: Examples to guide evaluation. Defaults to None.
            min_score: Minimum possible score. Defaults to 0.0.
            max_score: Maximum possible score. Defaults to 1.0.
            threshold: Success threshold. Defaults to midpoint.
            threshold_operator: Operator for threshold comparison.
            name: Unique name for this metric.
            description: Description of what this metric measures.
            metric_type: Type of metric (defaults to CONVERSATIONAL).
            model: LLM model to use for evaluation.
            **kwargs: Additional keyword arguments.

        Raises:
            ValueError: If score range or threshold is invalid.

        Note:
            When evaluation_prompt, evaluation_steps, or reasoning are None, the Jinja2
            template will use built-in defaults for goal achievement evaluation. This allows
            for quick setup while still supporting full customization.
        """

        self.config = GoalAchievementJudgeConfig(
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            reasoning=reasoning,
            evaluation_examples=evaluation_examples,
            min_score=min_score,
            max_score=max_score,
            threshold=threshold,
            threshold_operator=threshold_operator,
            name=name or "goal_achievement",
            description=description or "Evaluates how well a conversation achieves its stated goal",
            metric_type=metric_type or MetricType.CONVERSATIONAL,
            score_type=SCORE_TYPE,
            class_name=self.__class__.__name__,
        )
        super().__init__(config=self.config, model=model)

        self.min_score = self.config.min_score
        self.max_score = self.config.max_score
        self.threshold = self.config.threshold
        self.threshold_operator = self.config.threshold_operator

        # Set up Jinja environment
        self._setup_jinja_environment()

    def _get_prompt_template(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
        **additional_template_vars,
    ) -> str:
        """
        Generate the prompt using the base class with numeric-specific variables.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional conversation goal
            **additional_template_vars: Additional template variables

        Returns:
            The rendered prompt template
        """
        return super()._get_prompt_template(
            conversation_history=conversation_history,
            goal=goal,
            min_score=self.min_score,
            max_score=self.max_score,
            **additional_template_vars,
        )

    def evaluate(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
    ) -> MetricResult:
        """
        Evaluate goal achievement in the conversation.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional explicit goal statement. If not provided, the goal
                  should be inferred from the conversation context.

        Returns:
            MetricResult with:
                - score: Numeric score (within min_score to max_score)
                - details: Detailed evaluation information including:
                    - score: The numeric score
                    - score_type: "numeric"
                    - prompt: The full evaluation prompt
                    - reason: The LLM's reasoning for the score
                    - is_successful: Whether the score meets the threshold
                    - threshold_operator: The operator used for threshold comparison
                    - min_score: Minimum possible score
                    - max_score: Maximum possible score
                    - threshold: The threshold value for success
                    - turn_count: Number of turns in the conversation
                    - goal: The goal that was evaluated

        Raises:
            ValueError: If validation fails
        """
        # Validate inputs
        self._validate_evaluate_inputs(conversation_history, goal)

        # Generate the evaluation prompt
        prompt = self._get_prompt_template(conversation_history, goal)

        # Base details dictionary
        details = self._get_base_details(prompt)

        threshold_operator_value = (
            (
                self.threshold_operator.value
                if isinstance(self.threshold_operator, ThresholdOperator)
                else str(self.threshold_operator)
            )
            if self.threshold_operator
            else None
        )

        details.update(
            {
                "threshold_operator": threshold_operator_value,
                "min_score": self.min_score,
                "max_score": self.max_score,
                "threshold": self.threshold,
                "turn_count": len(conversation_history),
                "goal": goal or "Infer from conversation",
            }
        )

        try:
            # Run the evaluation with structured response model
            response = self.model.generate(prompt, schema=GoalAchievementScoreResponse)
            response = GoalAchievementScoreResponse(**response)  # type: ignore

            # Get the score and reason from the response
            score = response.score
            reason = response.reason

            # Check if the evaluation meets the threshold
            is_successful = self._evaluate_score(score=score)

            # Update details with success-specific fields
            details.update(
                {
                    "score": score,
                    "reason": reason,
                    "is_successful": is_successful,
                }
            )

            return MetricResult(score=score, details=details)

        except Exception as e:
            return self._handle_evaluation_error(e, details, 0.0)

    def _evaluate_score(self, score: float) -> bool:
        """
        Evaluate if a score meets the success criteria.

        Args:
            score: The score to evaluate

        Returns:
            True if the score meets the threshold criteria, False otherwise
        """
        # Ensure threshold_operator is ThresholdOperator enum
        operator = (
            self.threshold_operator
            if isinstance(self.threshold_operator, ThresholdOperator)
            else ThresholdOperator(self.threshold_operator)
        )
        threshold_func = OPERATOR_MAP[operator]
        result = threshold_func(score, self.threshold)
        return result

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "GoalAchievementJudge":
        """Create a metric from a dictionary."""
        # Get all field names from the dataclass
        valid_fields = {field.name for field in fields(GoalAchievementJudgeConfig)}

        # Filter config to only include keys that exist in the dataclass
        filtered_config = {k: v for k, v in config.items() if k in valid_fields}

        return cls.from_config(GoalAchievementJudgeConfig(**filtered_config))

