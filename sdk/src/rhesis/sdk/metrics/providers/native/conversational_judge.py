"""Base class for native Rhesis conversational metrics using LLM-as-judge."""

from pathlib import Path
from typing import Any, Dict, Optional, TypeVar, Union

from pydantic import BaseModel, Field

from rhesis.sdk.metrics.base import MetricResult, MetricType, ScoreType
from rhesis.sdk.metrics.constants import OPERATOR_MAP, ThresholdOperator
from rhesis.sdk.metrics.conversational.base import ConversationalMetricBase
from rhesis.sdk.metrics.conversational.types import ConversationHistory
from rhesis.sdk.metrics.providers.native.configs import ConversationalNumericConfig
from rhesis.sdk.metrics.providers.native.evaluation_patterns import NumericEvaluationMixin
from rhesis.sdk.metrics.providers.native.serialization import BackendSyncMixin, SerializationMixin
from rhesis.sdk.metrics.providers.native.shared_utils import (
    get_base_details,
    handle_evaluation_error,
    setup_jinja_environment,
)
from rhesis.sdk.models import BaseLLM

# Default value when goal is not specified
GOAL_DEFAULT = "Infer from conversation"

# Type variable for generic return types
T = TypeVar("T", bound="ConversationalJudge")


class ConversationalScoreResponse(BaseModel):
    """Response schema for conversational judge evaluation."""

    score: float = Field(
        description="Numeric score between min_score and max_score indicating quality of the conversation"
    )
    reason: str = Field(
        description="Detailed reasoning for the assigned score, referencing specific parts of the conversation"
    )


class ConversationalJudge(
    ConversationalMetricBase, SerializationMixin, BackendSyncMixin, NumericEvaluationMixin
):
    """
    Base class for native Rhesis conversational metrics using LLM-as-judge.

    Provides:
    - Jinja template rendering for conversation evaluation prompts
    - Structured output support
    - Numeric scoring with threshold-based success criteria (default)
    - Error handling
    - Common evaluation patterns

    This mirrors the JudgeBase class pattern for single-turn metrics, adapted
    for conversational (multi-turn) evaluation. By default, all conversational
    judges use numeric scoring (0-1 scale with thresholds), following the
    DeepEval pattern.

    **Numeric Scoring (Default)**:
    All conversational judges are numeric by default. Use the inherited
    `_evaluate_score()` method to check if a score meets the threshold:

    ```python
    class MyNumericJudge(ConversationalJudge):
        def evaluate(self, conversation_history, **kwargs):
            # Get numeric score from LLM
            score = self._get_llm_score(conversation_history)

            # Use inherited method for threshold comparison
            is_successful = self._evaluate_score(score)

            return MetricResult(
                score=score,
                details={"is_successful": is_successful, ...}
            )
    ```

    **Categorical Scoring (Future Extension)**:
    For rare categorical cases, override the `evaluate()` method and ignore
    the numeric fields. The numeric fields (min_score, max_score, threshold)
    will still be present but unused:

    ```python
    class SafetyJudge(ConversationalJudge):
        def __init__(self, categories=None, passing_categories=None, **kwargs):
            super().__init__(**kwargs)
            # Don't use min_score, max_score, threshold
            self.categories = categories or ["safe", "risky", "unsafe"]
            self.passing_categories = passing_categories or ["safe"]

        def evaluate(self, conversation_history, **kwargs):
            # Return categorical score - don't use _evaluate_score()
            category = self._get_llm_category(conversation_history)
            is_successful = category in self.passing_categories

            return MetricResult(
                score=category,
                details={"is_successful": is_successful, ...}
            )
    ```

    Note: Most conversational metrics are naturally numeric (goal achievement,
    coherence, fluency, turn quality). Categorical scoring should only be used
    when truly necessary.
    """

    def __init__(
        self,
        config: Optional[ConversationalNumericConfig] = None,
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
        Initialize conversational judge.

        Args:
            config: Metric configuration with judge-specific fields. If None, creates config from other parameters.
            evaluation_prompt: The main evaluation criteria. Used if config is None.
            evaluation_steps: Step-by-step evaluation process. Used if config is None.
            reasoning: Guidelines for reasoning. Used if config is None.
            evaluation_examples: Examples to guide evaluation. Used if config is None.
            min_score: Minimum possible score. Defaults to 0.0. Used if config is None.
            max_score: Maximum possible score. Defaults to 1.0. Used if config is None.
            threshold: Success threshold. Defaults to midpoint. Used if config is None.
            threshold_operator: Operator for threshold comparison. Used if config is None.
            name: Unique name for this metric. Used if config is None.
            description: Description of what this metric measures. Used if config is None.
            metric_type: Type of metric (defaults to CONVERSATIONAL). Used if config is None.
            model: LLM model for evaluation.
            **kwargs: Additional keyword arguments.

        Note:
            Either provide a config object OR the individual parameters. If config is provided,
            individual parameters are ignored. This allows for both legacy usage (with config)
            and modern usage (with direct parameters like GoalAchievementJudge).
        """
        # If config is provided, use it directly (legacy mode)
        if config is not None:
            self.config = config
        else:
            # Create config from individual parameters (modern mode)
            self.config = ConversationalNumericConfig(
                evaluation_prompt=evaluation_prompt,
                evaluation_steps=evaluation_steps,
                reasoning=reasoning,
                evaluation_examples=evaluation_examples,
                min_score=min_score,
                max_score=max_score,
                threshold=threshold,
                threshold_operator=threshold_operator,
                name=name or "conversational_judge",
                description=description or "Evaluates conversational interactions",
                metric_type=metric_type or MetricType.CONVERSATIONAL,
                score_type=ScoreType.NUMERIC,
                class_name=self.__class__.__name__,
            )

        super().__init__(config=self.config, model=model)
        self.evaluation_prompt = self.config.evaluation_prompt
        self.evaluation_steps = self.config.evaluation_steps
        self.reasoning = self.config.reasoning
        self.evaluation_examples = self.config.evaluation_examples

        # Numeric scoring fields (available to all conversational judges)
        self.min_score = self.config.min_score
        self.max_score = self.config.max_score
        self.threshold = self.config.threshold
        self.threshold_operator = self.config.threshold_operator

        # Set up Jinja environment
        self._setup_jinja_environment()

    def _setup_jinja_environment(self) -> None:
        """Set up Jinja2 environment for template rendering."""
        self.jinja_env = setup_jinja_environment()

    def _get_prompt_template(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
        **additional_template_vars,
    ) -> str:
        """
        Generate the evaluation prompt using Jinja2 template.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional conversation goal
            **additional_template_vars: Additional variables for template rendering

        Returns:
            Rendered prompt string
        """
        # Load the template
        template_path = Path(__file__).parent / "templates" / "conversational_prompt_metric.jinja"

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
        except FileNotFoundError:
            # Fallback to a simple template if file doesn't exist
            template_content = """
{{ evaluation_prompt or "Evaluate the quality of this conversation." }}

{% if evaluation_steps %}
{{ evaluation_steps }}
{% endif %}

{% if reasoning %}
{{ reasoning }}
{% endif %}

{% if evaluation_examples %}
Examples:
{{ evaluation_examples }}
{% endif %}

Conversation to evaluate:
{% for message in conversation_history %}
{{ message.role }}: {{ message.content }}
{% endfor %}

{% if goal %}
Goal: {{ goal }}
{% endif %}

Provide your evaluation as a numeric score between {{ min_score }} and {{ max_score }}.
            """.strip()

        template = self.jinja_env.from_string(template_content)

        # Prepare template variables
        template_vars = {
            "conversation_history": conversation_history,
            "goal": goal or GOAL_DEFAULT,
            "evaluation_prompt": self.evaluation_prompt,
            "evaluation_steps": self.evaluation_steps,
            "reasoning": self.reasoning,
            "evaluation_examples": self.evaluation_examples,
            "min_score": self.min_score,
            "max_score": self.max_score,
            "threshold": self.threshold,
            **additional_template_vars,
        }

        # Render the template
        prompt = template.render(**template_vars)
        return prompt

    def evaluate(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
    ) -> MetricResult:
        """
        Evaluate the conversation using the configured criteria.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional explicit goal statement

        Returns:
            MetricResult with numeric score and detailed evaluation information
        """
        # Validate inputs
        self._validate_evaluate_inputs(conversation_history, goal)

        # Generate the evaluation prompt
        prompt = self._get_prompt_template(conversation_history, goal)

        # Use the shared numeric evaluation pattern
        return self._execute_numeric_evaluation(
            prompt=prompt,
            response_schema=ConversationalScoreResponse,
            additional_details={
                "turn_count": len(conversation_history),
                "goal": goal or GOAL_DEFAULT,
            },
        )

    def _validate_evaluate_inputs(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
    ) -> None:
        """
        Validate inputs for conversational evaluation.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional conversation goal

        Raises:
            ValueError: If validation fails
        """
        if not isinstance(conversation_history, ConversationHistory):
            raise ValueError("conversation_history must be a ConversationHistory instance")

        if len(conversation_history) == 0:
            raise ValueError("conversation_history cannot be empty")

        if goal is not None and not isinstance(goal, str):
            raise ValueError("goal must be a string or None")

    def _get_base_details(self, prompt: str) -> Dict[str, Any]:
        """
        Get base details dictionary common to all conversational metrics.

        Args:
            prompt: The evaluation prompt

        Returns:
            Base details dictionary
        """
        return get_base_details(self.score_type, prompt, metric_name=self.name)

    def _handle_evaluation_error(
        self, e: Exception, details: Dict[str, Any], default_score: Any
    ) -> MetricResult:
        """
        Handle evaluation errors with consistent logging and error details.

        Args:
            e: The exception that occurred
            details: Details dictionary to update
            default_score: Default score to return on error

        Returns:
            Error result with default score
        """
        return handle_evaluation_error(e, self.name, self.model, details, default_score)

    def _setup_jinja_environment(self) -> None:
        """
        Set up Jinja environment for template rendering.

        This method initializes a Jinja2 environment with the templates directory
        and configures it for optimal template rendering performance.
        """
        templates_dir = Path(__file__).resolve().parent / "templates"
        self.jinja_env = setup_jinja_environment(templates_dir)

    def _get_prompt_template(
        self,
        conversation_history: ConversationHistory,
        goal: Optional[str] = None,
        **additional_template_vars,
    ) -> str:
        """
        Generate the prompt to be sent to the LLM using a Jinja template.

        Args:
            conversation_history: The conversation to evaluate
            goal: Optional conversation goal
            **additional_template_vars: Additional template variables

        Returns:
            The rendered prompt template

        Raises:
            ValueError: If template loading or rendering fails
        """
        try:
            # Load the template
            template = self.jinja_env.get_template("conversational_prompt_metric.jinja")
        except Exception as e:
            raise ValueError(f"Failed to load template: {e}") from e

        if self.score_type is None:
            raise ValueError("score_type must be set before calling _get_prompt_template")

        # Format conversation as readable text
        conversation_text = self._format_conversation(conversation_history)

        score_type_value = (
            self.score_type.value
            if isinstance(self.score_type, ScoreType)
            else str(self.score_type)
        )

        # Prepare base template variables
        template_vars = {
            "evaluation_prompt": self.evaluation_prompt,
            "evaluation_steps": self.evaluation_steps,
            "reasoning": self.reasoning,
            "evaluation_examples": self.evaluation_examples,
            "conversation_text": conversation_text,
            "goal": goal or GOAL_DEFAULT,
            "turn_count": len(conversation_history),
            "score_type": score_type_value,
        }

        # Add any additional template variables specific to the metric type
        template_vars.update(additional_template_vars)

        try:
            # Render the template with all required variables
            prompt = template.render(**template_vars)
        except Exception as e:
            raise ValueError(f"Failed to render template: {e}") from e

        return prompt

    def _format_conversation(self, conversation_history: ConversationHistory) -> str:
        """
        Format conversation history as readable text for the prompt.

        Args:
            conversation_history: The conversation to format

        Returns:
            Formatted conversation text
        """
        simple_turns = conversation_history.get_simple_turns()
        formatted_turns = []

        for i, turn in enumerate(simple_turns, 1):
            role = turn["role"]
            content = turn["content"]
            formatted_turns.append(f"Turn {i} [{role}]: {content}")

        return "\n\n".join(formatted_turns)

    def _evaluate_score(self, score: float) -> bool:
        """
        Evaluate if a numeric score meets the success criteria.

        This method is available to all conversational judges for threshold-based
        evaluation. Uses the threshold and threshold_operator from the configuration.

        Args:
            score: The numeric score to evaluate

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
