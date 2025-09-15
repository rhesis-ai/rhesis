from typing import List, Optional, Union

from pydantic import BaseModel, Field

from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.constants import OPERATOR_MAP, ScoreType, ThresholdOperator
from rhesis.sdk.metrics.providers.native.prompt_metric import (
    RhesisPromptMetricBase,
)


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
        name: str,
        evaluation_prompt: str,
        evaluation_steps: str,
        reasoning: str,
        evaluation_examples: str = "",
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        threshold: Optional[float] = None,
        threshold_operator: Union[ThresholdOperator, str] = ThresholdOperator.GREATER_THAN_OR_EQUAL,
        model: Optional[str] = None,
        metric_type="rag",
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
            metric_type (str, optional): Type of metric for categorization. Defaults to "rag".
            **kwargs: Additional keyword arguments passed to the base class

        Raises:
            ValueError: If only min_score or only max_score is provided (both required together)
            ValueError: If threshold is outside the [min_score, max_score] range
            ValueError: If threshold_operator string is invalid
        """
        super().__init__(
            name=name,
            metric_type=metric_type,
            model=model,
            **kwargs,
        )
        # Convert string to enum if needed
        self.score_type = ScoreType.NUMERIC
        if isinstance(threshold_operator, str):
            threshold_operator = ThresholdOperator(threshold_operator)
        self.threshold_operator = threshold_operator
        self.model = model

        # Validate and set up numeric score parameters
        self._validate_score_range(min_score, max_score)
        self._set_score_parameters(min_score, max_score, threshold)

        # Store other parameters
        self.evaluation_prompt = evaluation_prompt
        self.evaluation_steps = evaluation_steps
        self.reasoning = reasoning
        self.evaluation_examples = evaluation_examples

        # Set up Jinja environment
        self._setup_jinja_environment()

    def _validate_score_range(self, min_score: Optional[float], max_score: Optional[float]) -> None:
        """
        Validate that min_score and max_score are provided together.

        Args:
            min_score (Optional[float]): Minimum score value
            max_score (Optional[float]): Maximum score value

        Raises:
            ValueError: If only one of min_score or max_score is provided
        """
        if min_score is not None and max_score is None:
            raise ValueError("Only min_score was set, please set max_score")

        if min_score is None and max_score is not None:
            raise ValueError("Only max_score was set, please set min_score")

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

    def _get_prompt_template(
        self, input: str, output: str, expected_output: str, context: List[str] = None
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
        self, input: str, output: str, expected_output: Optional[str], context: List[str] = None
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
        if expected_output is None and self.requires_ground_truth:
            raise ValueError(f"{self.name} metric requires ground truth but none was provided")

        # Generate the evaluation prompt
        prompt = self._get_prompt_template(input, output, expected_output or "", context or [])

        # Base details dictionary with common fields
        details = {
            "score_type": self.score_type.value,
            "prompt": prompt,
            "threshold_operator": (
                self.threshold_operator.value if self.threshold_operator else None
            ),
            "min_score": self.min_score,
            "max_score": self.max_score,
            "threshold": self.threshold,
        }

        try:
            # Run the evaluation with structured response model
            response = self._model.generate(prompt, schema=NumericScoreResponse)
            response = NumericScoreResponse(**response)

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
            # Log the error for debugging with full traceback
            import logging
            import traceback

            logger = logging.getLogger(__name__)

            error_msg = f"Error evaluating with {self.name}: {str(e)}"
            logger.error(f"Exception in RhesisPromptMetric.evaluate: {error_msg}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception details: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            # Update details with error-specific fields
            details.update(
                {
                    "error": error_msg,
                    "reason": error_msg,
                    "exception_type": type(e).__name__,
                    "exception_details": str(e),
                    "model": self.model,
                }
            )

            # Return a default minimal score for numeric
            return MetricResult(score=0.0, details=details)

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


if __name__ == "__main__":
    """
    Example usage of RhesisPromptMetricNumeric for evaluating text quality.
    
    This example demonstrates how to create and use a numeric prompt metric
    to evaluate the quality of generated text responses.
    """

    # Example 1: Basic usage with default parameters
    print("=== Example 1: Basic Usage ===")

    # Create a metric for evaluating answer quality
    quality_metric = RhesisPromptMetricNumeric(
        name="answer_quality_evaluator",
        evaluation_prompt="""
        Evaluate the quality of the provided answer based on the following criteria:
        1. Accuracy: How correct and factual is the information?
        2. Completeness: Does it fully address the question?
        3. Clarity: Is the answer clear and well-structured?
        4. Relevance: How relevant is the answer to the question asked?
        """,
        evaluation_steps="""
        1. Read the question and the provided answer carefully
        2. Check the answer against the expected output for accuracy
        3. Assess completeness by checking if all aspects of the question are addressed
        4. Evaluate clarity and structure of the response
        5. Determine overall relevance to the original question
        6. Assign a score from 0.0 to 1.0 based on these criteria
        """,
        reasoning="""
        Consider the context provided and compare the answer with the expected output.
        A perfect answer (1.0) should be completely accurate, fully address the question,
        be clearly written, and highly relevant. Lower scores should reflect deficiencies
        in any of these areas.
        """,
        evaluation_examples="""
        Example 1:
        Question: "What is the capital of France?"
        Answer: "Paris"
        Expected: "The capital of France is Paris"
        Score: 0.9 (accurate but not complete)
        
        Example 2:
        Question: "What is the capital of France?"
        Answer: "The capital of France is Paris, located in the north-central part of the country."
        Expected: "The capital of France is Paris"
        Score: 1.0 (accurate, complete, and well-structured)
        """,
        min_score=0.0,
        max_score=1.0,
        threshold=0.7,  # 70% threshold for success
        threshold_operator=ThresholdOperator.GREATER_THAN_OR_EQUAL,
        model="gemini",
    )

    # Example data for evaluation
    test_input = "What are the main benefits of renewable energy?"
    test_output = "Renewable energy sources like solar and wind power are clean, sustainable, and help reduce greenhouse gas emissions. They also create jobs and reduce dependence on fossil fuels."
    expected_output = "The main benefits of renewable energy include: 1) Environmental benefits - reduced greenhouse gas emissions and air pollution, 2) Economic benefits - job creation and energy cost savings, 3) Energy security - reduced dependence on foreign fossil fuels, 4) Sustainability - inexhaustible energy sources"

    result = quality_metric.evaluate(
        input=test_input, output=test_output, expected_output=expected_output
    )

    print(f"Score: {result.score}")
    print(f"Is Successful: {result.details['is_successful']}")
    print(f"Reason: {result.details['reason']}")
    print(f"Threshold: {result.details['threshold']}")
    print(f"Score Range: {result.details['min_score']} - {result.details['max_score']}")
