from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import create_model

from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.constants import ScoreType
from rhesis.sdk.metrics.providers.native.prompt_metric import (
    RhesisPromptMetricBase,
)


class RhesisPromptMetricCategorical(RhesisPromptMetricBase):
    """
    A generic metric that evaluates outputs based on a custom prompt template.
    Uses LLM to perform evaluation based on provided evaluation criteria.
    """

    def __init__(
        self,
        name: str,
        evaluation_prompt: str,
        evaluation_steps: str,
        reasoning: str,
        categories: List[str],
        passing_categories: Union[str, List[str]],
        evaluation_examples: str = "",
        model: Optional[str] = None,
        metric_type: str = "rag",
        **kwargs,
    ):
        """
        Initialize the categorical prompt metric.

        Args:
            name (str): Unique name for this metric instance
            evaluation_prompt (str): The main evaluation criteria and instructions for the LLM
            evaluation_steps (str): Step-by-step process the LLM should follow for evaluation
            reasoning (str): Guidelines for the LLM's reasoning process during evaluation
            categories (List[str]): List of valid categories the LLM can return.
                Must contain at least 2 scores.
            passing_categories (Union[str, List[str]]): Category(s) considered successful/passing.
                Can be a single string or list of strings. All values must be present in
                categories.
            evaluation_examples (str, optional): Examples to guide the LLM's evaluation.
                Defaults to empty string.
            model (Optional[str], optional): The LLM model to use for evaluation.
                If None, uses the default model. Defaults to None.
            metric_type (str, optional): Type of metric for categorization. Defaults to "rag".
            **kwargs: Additional keyword arguments passed to the base class

        Raises:
            ValueError: If categories has fewer than 2 items
            ValueError: If passing_categories is not a string or list
            ValueError: If passing_categories contains values not in categories
            ValueError: If the number of passing_categories exceeds categories
        """
        super().__init__(
            name=name,
            metric_type=metric_type,
            model=model,
            **kwargs,
        )
        # Convert string to enum if needed
        self.score_type = ScoreType.CATEGORICAL
        self.categories = categories
        self.passing_categories = passing_categories
        self.model = model

        # Validate input parameters
        self._validate_categories()
        self._validate_passing_categories()
        self._normalize_passing_categories()
        self._validate_passing_categories_subset()

        # Store other parameters
        self.evaluation_prompt = evaluation_prompt
        self.evaluation_steps = evaluation_steps
        self.reasoning = reasoning
        self.evaluation_examples = evaluation_examples

        # Set up Jinja environment
        self._setup_jinja_environment()

    def _validate_categories(self) -> None:
        """
        Validate that categories is a valid list with at least 2 scores.

        Raises:
            ValueError: If categories is not a list or has fewer than 2 items
        """
        if not isinstance(self.categories, list) or len(self.categories) < 2:
            raise ValueError(
                f"categories must be a list with at least 2 scores, got: {self.categories}"
            )

    def _validate_passing_categories(self) -> None:
        """
        Validate that passing_categories is a string or list.

        Raises:
            ValueError: If passing_categories is not a string or list
        """
        if not isinstance(self.passing_categories, (str, list)):
            raise ValueError(
                f"passing_categories must be a string or list, got: {type(self.passing_categories)}"
            )

    def _normalize_passing_categories(self) -> None:
        """
        Convert string passing_categories to list for consistent handling.

        This method ensures that passing_categories is always a list, converting
        single string values to single-item lists.
        """
        if isinstance(self.passing_categories, str):
            self.passing_categories = [self.passing_categories]

    def _validate_passing_categories_subset(self) -> None:
        """
        Validate that passing_categories is a subset of categories.

        Raises:
            ValueError: If passing_categories contains values not in categories
            ValueError: If passing_categories has more items than categories
        """
        if len(self.passing_categories) > len(self.categories):
            raise ValueError(
                f"The number of passing_categories ({len(self.passing_categories)}) must be "
                f"less than or equal to the number of categories ({len(self.categories)})"
            )

        if not set(self.passing_categories).issubset(set(self.categories)):
            missing_scores = set(self.passing_categories) - set(self.categories)
            raise ValueError(
                f"Each value in passing_categories must be present in categories. "
                f"Missing scores: {missing_scores}\n"
                f"Given passing_categories: {self.passing_categories}\n"
                f"Given categories: {self.categories}"
            )

    def _get_prompt_template(
        self, input: str, output: str, expected_output: str, context: Optional[List[str]] = None
    ) -> str:
        """
        Generate the prompt to be sent to the LLM using a Jinja template.

        This method uses the base class implementation with categorical-specific template variables.

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
            categories=self.categories,
            passing_categories=self.passing_categories,
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
        categorical score and detailed evaluation information.

        Args:
            input (str): The input query/question that was posed to the system
            output (str): The system's response/output that needs to be evaluated
            expected_output (Optional[str]): The expected or reference output (ground truth).
                Required for this metric as it requires ground truth for evaluation.
            context (Optional[List[str]], optional): List of context chunks used for the response.
                Defaults to None.

        Returns:
            MetricResult: The evaluation result containing:
                - score (str): The categorical score returned by the LLM (one of categories)
                - details (Dict[str, Any]): Detailed evaluation information including:
                    - score: The categorical score
                    - score_type: "categorical"
                    - prompt: The full evaluation prompt sent to the LLM
                    - reason: The LLM's reasoning for the score
                    - is_successful: Whether the score meets the success criteria
                    - categories: List of valid categories
                    - passing_categories: List of passing categories
                    - error: Error message if evaluation failed
                    - exception_type: Type of exception if evaluation failed
                    - exception_details: Detailed exception information if evaluation failed

        Raises:
            ValueError: If input is empty or not a string
            ValueError: If output is not a string
            ValueError: If expected_output is None (this metric requires ground truth)
            ValueError: If context is provided but not a list
            ValueError: If template rendering fails
            ValueError: If LLM response validation fails

        Note:
            The method handles various error conditions gracefully, returning error scores
            with detailed information rather than raising exceptions for LLM-related issues.
            Only input validation errors are raised as exceptions.
        """
        # Validate inputs
        if not isinstance(input, str) or not input.strip():
            raise ValueError("input must be a non-empty string")

        if not isinstance(output, str):
            raise ValueError("output must be a string")

        if expected_output is None and self.requires_ground_truth:
            raise ValueError(f"{self.name} metric requires ground truth but none was provided")

        if context is not None and not isinstance(context, list):
            raise ValueError("context must be a list of strings or None")

        # Generate the evaluation prompt
        prompt = self._get_prompt_template(input, output, expected_output or "", context or [])

        # Initialize common details fields
        details: Dict[str, Any] = {
            "score_type": self.score_type.value,
            "prompt": prompt,
            "categories": self.categories,
            "passing_categories": self.passing_categories,
        }

        try:
            # Run the evaluation with structured response model
            # Create a proper Literal type from the possible scores
            if len(self.categories) == 1:
                score_literal = Literal[self.categories[0]]
            else:
                # Create individual string literals - use a more compatible approach
                score_literal = Literal[tuple(self.categories)]

            ScoreResponseCategorical = create_model(
                "ScoreResponseCategorical", score=(score_literal, ...), reason=(str, ...)
            )
            response = self._model.generate(prompt, schema=ScoreResponseCategorical)
            response = ScoreResponseCategorical(**response)

            # Get the score directly from the response
            score = response.score
            reason = response.reason

            # Check if the evaluation meets the reference score using the base class method
            is_successful = self._evaluate_score(
                score=score,
                passing_categories=self.passing_categories,
            )

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
            # Log unexpected errors for debugging
            import logging
            import traceback

            logger = logging.getLogger(__name__)
            error_msg = f"Unexpected error evaluating with {self.name}: {str(e)}"
            logger.error(f"Exception in RhesisPromptMetric.evaluate: {error_msg}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception details: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            # Update details with error-specific fields
            details.update(
                {
                    "error": error_msg,
                    "reason": f"Unexpected error: {str(e)}",
                    "exception_type": type(e).__name__,
                    "exception_details": str(e),
                    "model": self.model,
                    "is_successful": False,
                }
            )

            # Return a default failure score for categorical metrics
            return MetricResult(score="error", details=details)

    def _evaluate_score(self, score: str, passing_categories: List[str]) -> bool:
        """
        Evaluate if a score meets the success criteria for categorical metrics.

        This method checks if the provided score is present in the list of passing categories.

        Args:
            score (str): The score to evaluate
            passing_categories (List[str]): List of categories considered passing

        Returns:
            bool: True if the score is in passing_categories, False otherwise
        """
        result = score in passing_categories
        return result
