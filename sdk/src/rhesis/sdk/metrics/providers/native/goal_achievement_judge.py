"""Goal Achievement Judge for evaluating conversation goal completion."""

from dataclasses import fields
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from rhesis.sdk.metrics.base import MetricResult, MetricType, ScoreType
from rhesis.sdk.metrics.constants import ThresholdOperator
from rhesis.sdk.metrics.conversational.types import ConversationHistory
from rhesis.sdk.metrics.providers.native.configs import ConversationalNumericConfig
from rhesis.sdk.metrics.providers.native.conversational_judge import (
    GOAL_DEFAULT,
    ConversationalJudge,
)
from rhesis.sdk.metrics.providers.native.evaluation_patterns import NumericEvaluationMixin
from rhesis.sdk.models import BaseLLM

SCORE_TYPE = ScoreType.NUMERIC


class CriterionEvaluation(BaseModel):
    """Evaluation of a single goal criterion."""

    criterion: str = Field(description="The specific criterion being evaluated")
    met: bool = Field(description="Whether this criterion was met")
    evidence: str = Field(description="Specific evidence from the conversation for this criterion")
    relevant_turns: List[int] = Field(
        default_factory=list,
        description=(
            "List of turn numbers (1-indexed) that are relevant to this criterion. "
            "Include all turns where evidence for or against this criterion was observed."
        ),
    )


class GoalAchievementScoreResponse(BaseModel):
    """
    Structured response from LLM goal evaluation.

    Includes criterion-by-criterion breakdown for programmatic analysis.
    """

    score: float = Field(description="Goal achievement score (0.0 to 1.0)")
    reason: str = Field(description="Overall explanation for the score")

    # Structured criterion evaluation
    criteria_evaluations: List[CriterionEvaluation] = Field(
        description=(
            "Break down the goal into individual measurable criteria and evaluate each one. "
            "This enables detailed analysis of exactly what was/wasn't achieved."
        )
    )
    all_criteria_met: bool = Field(
        description="True only if ALL criteria evaluations have met=True"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the overall assessment (0.0 to 1.0)",
    )


class GoalAchievementJudge(ConversationalJudge, NumericEvaluationMixin):
    """
    Native conversational metric that evaluates goal achievement in conversations.

    This judge evaluates whether a conversation successfully achieves its stated goal,
    providing a numeric score based on how well the assistant helped the user reach
    their objective.

    The default prompt template includes built-in goal achievement criteria that are
    used when custom prompts are not provided. These defaults can be overridden by
    passing custom values for evaluation_prompt, evaluation_steps, or reasoning.
    """

    @property
    def is_goal_achievement_metric(self) -> bool:
        """
        Identify this metric as a goal achievement metric.

        This property is used by systems like Penelope to determine whether
        to create simplified summary versions of this metric's results to
        avoid duplication with detailed goal evaluation data.

        Returns:
            True for GoalAchievementJudge, False for other metrics
        """
        return True

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
        model: Optional[Union[BaseLLM, str]] = None,
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
            model: Language model to use for evaluation.
            **kwargs: Additional keyword arguments.

        Raises:
            ValueError: If score range or threshold is invalid.

        Note:
            When evaluation_prompt, evaluation_steps, or reasoning are None, the Jinja2
            template will use built-in defaults for goal achievement evaluation. This allows
            for quick setup while still supporting full customization.
        """

        # Use parent ConversationalNumericConfig which now includes numeric fields
        self.config = ConversationalNumericConfig(
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
        # Numeric fields are automatically initialized by ConversationalJudge parent
        super().__init__(config=self.config, model=model)

        # Set up Jinja environment
        self._setup_jinja_environment()

    def _get_prompt_template(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
        instructions: Optional[str] = None,
        **additional_template_vars,
    ) -> str:
        """
        Generate the prompt using the goal-achievement-specific template.

        This overrides the base class to use a specialized template with
        excellent defaults for goal achievement evaluation, incorporating
        best practices from Penelope's goal evaluation system.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional conversation goal
            instructions: Optional test instructions specifying HOW the test should be conducted
            **additional_template_vars: Additional template variables

        Returns:
            The rendered prompt template

        Raises:
            ValueError: If template loading or rendering fails
        """
        try:
            # Load the goal-achievement-specific template
            template = self.jinja_env.get_template("goal_achievement_prompt.jinja")
        except Exception as e:
            raise ValueError(f"Failed to load goal_achievement_prompt template: {e}") from e

        # Format conversation as readable text
        conversation_text = self._format_conversation(conversation_history)

        # Prepare template variables with goal-achievement-specific context
        template_vars = {
            "evaluation_prompt": self.evaluation_prompt,
            "evaluation_steps": self.evaluation_steps,
            "reasoning": self.reasoning,
            "evaluation_examples": self.evaluation_examples,
            "conversation_text": conversation_text,
            "goal": goal or GOAL_DEFAULT,
            "instructions": instructions,  # Add test instructions for context
            "turn_count": len(conversation_history),
            "min_score": self.min_score,
            "max_score": self.max_score,
        }

        # Add any additional template variables
        template_vars.update(additional_template_vars)

        try:
            # Render the template with all required variables
            prompt = template.render(**template_vars)
        except Exception as e:
            raise ValueError(f"Failed to render goal_achievement_prompt template: {e}") from e

        return prompt

    def evaluate(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> MetricResult:
        """
        Evaluate goal achievement in the conversation.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional explicit goal statement. If not provided, the goal
                  should be inferred from the conversation context.
            instructions: Optional test instructions that specify HOW the test
                  should be conducted (e.g., "send 6 exact messages", "do not stop early").
                  These provide critical context for evaluating whether the goal was
                  properly achieved.

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
                    - instructions: The test instructions (if provided)
                    - criteria_evaluations: List of CriterionEvaluation objects (breakdown)
                    - all_criteria_met: Whether all criteria were met
                    - confidence: Confidence level (0.0 to 1.0)

        Raises:
            ValueError: If validation fails
        """
        # Validate inputs
        self._validate_evaluate_inputs(conversation_history, goal)

        # Generate the evaluation prompt
        prompt = self._get_prompt_template(conversation_history, goal, instructions=instructions)

        # Use the shared numeric evaluation pattern with conversational-specific details
        return self._execute_numeric_evaluation(
            prompt=prompt,
            response_schema=GoalAchievementScoreResponse,
            additional_details={
                "turn_count": len(conversation_history),
                "goal": goal or GOAL_DEFAULT,
            },
        )

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "GoalAchievementJudge":
        """Create a metric from a dictionary."""
        # Get all field names from the dataclass
        valid_fields = {field.name for field in fields(ConversationalNumericConfig)}

        # Filter config to only include keys that exist in the dataclass
        filtered_config = {k: v for k, v in config.items() if k in valid_fields}

        return cls.from_config(ConversationalNumericConfig(**filtered_config))
