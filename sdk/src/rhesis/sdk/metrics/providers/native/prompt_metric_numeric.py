from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from rhesis.sdk.metrics.base import MetricResult, MetricType, ScoreType
from rhesis.sdk.metrics.constants import OPERATOR_MAP, ThresholdOperator
from rhesis.sdk.metrics.providers.native.prompt_metric import (
    PromptMetricConfig,
    RhesisPromptMetricBase,
)
from rhesis.sdk.models import BaseLLM

SCORE_TYPE = ScoreType.NUMERIC


@dataclass
class PromptMetricNumericConfig(PromptMetricConfig):
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
        """
        Validate that min_score and max_score are provided together.

        Args:
            min_score (Optional[float]): Minimum score value
            max_score (Optional[float]): Maximum score value

        Raises:
            ValueError: If only one of min_score or max_score is provided
            ValueError: If min_score and max_score are the same
            ValueError: If min_score is greater than max_score
        """
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
        """
        Set up score parameters with validation.

        This method sets the min_score, max_score, and threshold values with appropriate
        defaults and validation.

        Args:
            min_score (Optional[float]): Minimum possible score (defaults to 0.0)
            max_score (Optional[float]): Maximum possible score (defaults to 1.0)
            threshold (Optional[float]): Success threshold (defaults to midpoint)

        Raises:
            ValueError: If threshold is outside the [min_score, max_score] range
        """
        # For numeric scores, we need min_score, max_score, and threshold
        self.min_score = min_score if min_score is not None else 0
        self.max_score = max_score if max_score is not None else 1

        if threshold is None:
            self.threshold = self.min_score + (self.max_score - self.min_score) / 2
        else:
            self.threshold = threshold

        if not (self.min_score <= self.threshold <= self.max_score):
            raise ValueError(f"Threshold must be between {self.min_score} and {self.max_score}")


class NumericScoreResponse(BaseModel):
    """Model for structured numeric response from LLM evaluation."""

    score: float = Field(description="Evaluation score")
    reason: str = Field(description="Explanation for the score", default="")


class RhesisPromptMetricNumeric(RhesisPromptMetricBase):
    """
    A numeric metric that evaluates outputs based on a custom prompt template.
    Uses LLM to perform evaluation based on provided evaluation criteria.
    """

    def __init__(
        self,
        evaluation_prompt: str,
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
        Initialize the numeric prompt metric.

        Args:
            name (str): Unique name for this metric instance
            evaluation_prompt (str): The main evaluation criteria and instructions for the LLM
            evaluation_steps (str): Step-by-step process the LLM should follow for evaluation
            reasoning (str): Guidelines for the LLM's reasoning process during evaluation
            evaluation_examples (str, optional): Examples to guide the LLM's evaluation.
                Defaults to empty string.
            min_score (Optional[float], optional): Minimum possible score for evaluation.
                If provided, max_score must also be provided. Defaults to None (uses 0.0).
            max_score (Optional[float], optional): Maximum possible score for evaluation.
                If provided, min_score must also be provided. Defaults to None (uses 1.0).
            threshold (Optional[float], optional): Score threshold for determining success.
                If None, defaults to midpoint between min_score and max_score. Defaults to None.
            threshold_operator (Union[ThresholdOperator, str], optional): Operator for comparing
                score to threshold. Can be a ThresholdOperator enum or string. Defaults to None.
            model (Optional[str], optional): The LLM model to use for evaluation.
                If None, uses the default model. Defaults to None.
            **kwargs: Additional keyword arguments passed to the base class

        Raises:
            ValueError: If only min_score or only max_score is provided (both required together)
            ValueError: If threshold is outside the [min_score, max_score] range
            ValueError: If threshold_operator string is invalid
        """
        self.config = PromptMetricNumericConfig(
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            reasoning=reasoning,
            evaluation_examples=evaluation_examples,
            min_score=min_score,
            max_score=max_score,
            threshold=threshold,
            threshold_operator=threshold_operator,
            name=name,
            description=description,
            metric_type=metric_type,
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
        input: str,
        output: str,
        expected_output: str,
        context: Optional[List[str]] = None,
        **additional_template_vars,
    ) -> str:
        """
        Generate the prompt to be sent to the LLM using a Jinja template.

        This method uses the base class implementation with numeric-specific template variables.

        Args:
            input (str): The input query/question
            output (str): The system output/response
            expected_output (str): The expected or reference output
            context (Optional[List[str]], optional): List of context chunks used for the response.
                Defaults to None.

        Returns:
            str: The rendered prompt template ready to be sent to the LLM
        """
        return super()._get_prompt_template(
            input=input,
            output=output,
            expected_output=expected_output,
            context=context,
            min_score=self.min_score,
            max_score=self.max_score,
        )

    def evaluate(
        self,
        input: str,
        output: str,
        expected_output: Optional[str],
        context: Optional[List[str]] = None,
    ) -> MetricResult:
        """
        Evaluate the output using the LLM with the custom prompt template.

        This method generates a comprehensive evaluation prompt using the Jinja2 template
        system, sends it to the configured LLM, and returns a structured result with the
        numeric score and detailed evaluation information.

        Args:
            input (str): The input query/question that was posed to the system
            output (str): The system's response/output that needs to be evaluated
            expected_output (Optional[str]): The expected or reference output (ground truth).
                Required for this metric as it requires ground truth for evaluation.
            context (Optional[List[str]], optional): List of context chunks used for the response.
                Defaults to None.

        Returns:
            MetricResult: The evaluation result containing:
                - score (float): The numeric score returned by the LLM
                  (within min_score to max_score)
                - details (Dict[str, Any]): Detailed evaluation information including:
                    - score: The numeric score
                    - score_type: "numeric"
                    - prompt: The full evaluation prompt sent to the LLM
                    - reason: The LLM's reasoning for the score
                    - is_successful: Whether the score meets the threshold criteria
                    - threshold_operator: The operator used for threshold comparison
                    - min_score: Minimum possible score
                    - max_score: Maximum possible score
                    - threshold: The threshold value for success
                    - error: Error message if evaluation failed
                    - exception_type: Type of exception if evaluation failed
                    - exception_details: Detailed exception information if evaluation failed

        Raises:
            ValueError: If expected_output is None (this metric requires ground truth)

        Note:
            The method handles various error conditions gracefully, returning error scores
            with detailed information rather than raising exceptions for LLM-related issues.
            Only ground truth validation errors are raised as exceptions.
        """
        # Validate inputs using shared method
        self._validate_evaluate_inputs(input, output, expected_output, context)

        # Generate the evaluation prompt
        prompt = self._get_prompt_template(input, output, expected_output or "", context or [])

        # Base details dictionary with common fields
        details = self._get_base_details(prompt)
        details.update(
            {
                "threshold_operator": (
                    self.threshold_operator.value if self.threshold_operator else None
                ),
                "min_score": self.min_score,
                "max_score": self.max_score,
                "threshold": self.threshold,
            }
        )

        try:
            # Run the evaluation with structured response model
            response = self.model.generate(prompt, schema=NumericScoreResponse)
            response = NumericScoreResponse(**response)  # type: ignore

            # Get the score directly from the response
            score = response.score
            reason = response.reason

            # Check if the evaluation meets the threshold using the base class method
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
        Evaluate if a score meets the success criteria for numeric metrics.

        This method applies the threshold operator to compare the score against the threshold.

        Args:
            score (float): The score to evaluate
            threshold (float): The threshold value for comparison
            threshold_operator (ThresholdOperator): The operator to use for comparison

        Returns:
            bool: True if the score meets the threshold criteria, False otherwise
        """
        threshold_operator = OPERATOR_MAP[self.threshold_operator]
        result = threshold_operator(score, self.threshold)
        return result

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "RhesisPromptMetricNumeric":
        """Create a metric from a dictionary."""
        # Get all field names from the dataclass
        valid_fields = {field.name for field in fields(PromptMetricNumericConfig)}

        # Filter config to only include keys that exist in the dataclass
        filtered_config = {k: v for k, v in config.items() if k in valid_fields}

        return cls.from_config(PromptMetricNumericConfig(**filtered_config))


if __name__ == "__main__":

    class TestSchema(BaseModel):
        score: float
        reason: str

    output = {
        "score": 0.5,
        "reason": "This is a test reason",
    }
    response = TestSchema(**output)
