from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import create_model

from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.constants import ScoreType
from rhesis.sdk.metrics.providers.native.metric_base import (
    RhesisMetricBase,
)


class RhesisPromptMetricCategorical(RhesisMetricBase):
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
        possible_scores: List[str],
        successful_scores: Union[str, List[str]],
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
            possible_scores (List[str]): List of valid categorical scores the LLM can return.
                Must contain at least 2 scores.
            successful_scores (Union[str, List[str]]): Score(s) considered successful/passing.
                Can be a single string or list of strings. All values must be present in
                possible_scores.
            evaluation_examples (str, optional): Examples to guide the LLM's evaluation.
                Defaults to empty string.
            model (Optional[str], optional): The LLM model to use for evaluation.
                If None, uses the default model. Defaults to None.
            metric_type (str, optional): Type of metric for categorization. Defaults to "rag".
            **kwargs: Additional keyword arguments passed to the base class

        Raises:
            ValueError: If possible_scores has fewer than 2 items
            ValueError: If successful_scores is not a string or list
            ValueError: If successful_scores contains values not in possible_scores
            ValueError: If the number of successful_scores exceeds possible_scores
        """
        super().__init__(
            name=name,
            metric_type=metric_type,
            model=model,
        )
        # Convert string to enum if needed
        self.score_type = ScoreType.CATEGORICAL
        self.possible_scores = possible_scores
        self.successful_scores = successful_scores
        self.model = model

        # Validate input parameters
        self._validate_possible_scores()
        self._validate_successful_scores()
        self._normalize_successful_scores()
        self._validate_successful_scores_subset()

        # Store other parameters
        self.evaluation_prompt = evaluation_prompt
        self.evaluation_steps = evaluation_steps
        self.reasoning = reasoning
        self.evaluation_examples = evaluation_examples

        # Set up Jinja environment (cached for performance)
        self._setup_jinja_environment()

    def _validate_possible_scores(self) -> None:
        """
        Validate that possible_scores is a valid list with at least 2 scores.

        Raises:
            ValueError: If possible_scores is not a list or has fewer than 2 items
        """
        if not isinstance(self.possible_scores, list) or len(self.possible_scores) < 2:
            raise ValueError(
                f"possible_scores must be a list with at least 2 scores, "
                f"got: {self.possible_scores}"
            )

    def _validate_successful_scores(self) -> None:
        """
        Validate that successful_scores is a string or list.

        Raises:
            ValueError: If successful_scores is not a string or list
        """
        if not isinstance(self.successful_scores, (str, list)):
            raise ValueError(
                f"successful_scores must be a string or list, got: {type(self.successful_scores)}"
            )

    def _normalize_successful_scores(self) -> None:
        """
        Convert string successful_scores to list for consistent handling.

        This method ensures that successful_scores is always a list, converting
        single string values to single-item lists.
        """
        if isinstance(self.successful_scores, str):
            self.successful_scores = [self.successful_scores]

    def _validate_successful_scores_subset(self) -> None:
        """
        Validate that successful_scores is a subset of possible_scores.

        Raises:
            ValueError: If successful_scores contains values not in possible_scores
            ValueError: If successful_scores has more items than possible_scores
        """
        if len(self.successful_scores) > len(self.possible_scores):
            raise ValueError(
                f"The number of successful_scores ({len(self.successful_scores)}) must be "
                f"less than or equal to the number of possible_scores ({len(self.possible_scores)})"
            )

        if not set(self.successful_scores).issubset(set(self.possible_scores)):
            missing_scores = set(self.successful_scores) - set(self.possible_scores)
            raise ValueError(
                f"Each value in successful_scores must be present in possible_scores. "
                f"Missing scores: {missing_scores}\n"
                f"Given successful_scores: {self.successful_scores}\n"
                f"Given possible_scores: {self.possible_scores}"
            )

    def _setup_jinja_environment(self) -> None:
        """
        Set up Jinja environment for template rendering.

        This method initializes a Jinja2 environment with the templates directory
        and configures it for optimal template rendering performance.
        """
        templates_dir = Path(__file__).resolve().parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape("html", "xml"),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def requires_ground_truth(self) -> bool:
        """This metric typically requires ground truth."""
        return True

    def _get_prompt_template(
        self, input: str, output: str, expected_output: str, context: Optional[List[str]] = None
    ) -> str:
        """
        Generate the prompt to be sent to the LLM using a Jinja template.

        This method renders the Jinja2 template with all necessary variables to create
        a comprehensive evaluation prompt for the LLM.

        Args:
            input (str): The input query/question
            output (str): The system output/response
            expected_output (str): The expected or reference output
            context (Optional[List[str]], optional): List of context chunks used for the response.
                Defaults to None.

        Returns:
            str: The rendered prompt template ready to be sent to the LLM

        Raises:
            ValueError: If context format is invalid
            ValueError: If template loading fails
            ValueError: If template rendering fails
        """
        try:
            context_text = "\n".join(context) if context else "No context provided."
        except (TypeError, AttributeError) as e:
            raise ValueError(f"Invalid context format: {e}") from e

        try:
            # Load the template
            template = self.jinja_env.get_template("prompt_metric.jinja")
        except Exception as e:
            raise ValueError(f"Failed to load template: {e}") from e

        # Prepare template variables based on score type
        template_vars = {
            "evaluation_prompt": self.evaluation_prompt,
            "evaluation_steps": self.evaluation_steps,
            "reasoning": self.reasoning,
            "evaluation_examples": self.evaluation_examples,
            "input": input,
            "context_text": context_text,
            "expected_output": expected_output,
            "output": output,
            "score_type": self.score_type.value,
            "possible_scores": self.possible_scores,
            "successful_scores": self.successful_scores,
        }

        try:
            # Render the template with all required variables
            prompt = template.render(**template_vars)
        except Exception as e:
            raise ValueError(f"Failed to render template: {e}") from e

        return prompt

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
                - score (str): The categorical score returned by the LLM (one of possible_scores)
                - details (Dict[str, Any]): Detailed evaluation information including:
                    - score: The categorical score
                    - score_type: "categorical"
                    - prompt: The full evaluation prompt sent to the LLM
                    - reason: The LLM's reasoning for the score
                    - is_successful: Whether the score meets the success criteria
                    - possible_scores: List of valid scores
                    - successful_scores: List of successful scores
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

        try:
            # Run the evaluation with structured response model
            # Create a proper Literal type from the possible scores
            if len(self.possible_scores) == 1:
                score_literal = Literal[self.possible_scores[0]]
            else:
                # Create individual string literals - use a more compatible approach
                score_literal = Literal[tuple(self.possible_scores)]

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
                successful_scores=self.successful_scores,
            )

            # Prepare details based on score type
            details: Dict[str, Any] = {
                "score": score,
                "score_type": self.score_type.value,
                "prompt": prompt,
                "reason": reason,
                "is_successful": is_successful,
                "possible_scores": self.possible_scores,
                "successful_scores": self.successful_scores,
            }

            return MetricResult(score=score, details=details)

        except (ValueError, TypeError) as e:
            # Handle validation errors - these are user errors, don't log as errors
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Validation error in {self.name}: {str(e)}")

            details: Dict[str, Any] = {
                "error": f"Validation error: {str(e)}",
                "reason": f"Invalid input: {str(e)}",
                "exception_type": type(e).__name__,
                "exception_details": str(e),
                "model": self.model,
                "prompt": prompt,
                "score_type": self.score_type.value,
                "possible_scores": self.possible_scores,
                "successful_scores": self.successful_scores,
                "is_successful": False,
            }
            return MetricResult(score="error", details=details)

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

            # Return a fallback score with error information
            details: Dict[str, Any] = {
                "error": error_msg,
                "reason": f"Unexpected error: {str(e)}",
                "exception_type": type(e).__name__,
                "exception_details": str(e),
                "model": self.model,
                "prompt": prompt,
                "score_type": self.score_type.value,
                "possible_scores": self.possible_scores,
                "successful_scores": self.successful_scores,
                "is_successful": False,
            }

            # Return a default failure score for categorical metrics
            return MetricResult(score="error", details=details)

    def _evaluate_score(self, score: str, successful_scores: List[str]) -> bool:
        """
        Evaluate if a score meets the success criteria for categorical metrics.

        This method checks if the provided score is present in the list of successful scores.

        Args:
            score (str): The score to evaluate
            successful_scores (List[str]): List of scores considered successful

        Returns:
            bool: True if the score is in successful_scores, False otherwise
        """
        result = score in successful_scores
        return result


if __name__ == "__main__":
    # Example usage of RhesisPromptMetricCategorical
    print("Example: Creating a categorical metric for evaluating response quality")

    # Create a categorical metric for evaluating response quality
    metric = RhesisPromptMetricCategorical(
        name="response_quality_evaluator",
        evaluation_prompt=(
            "Evaluate the quality of the response based on accuracy, completeness, and helpfulness."
        ),
        evaluation_steps=(
            "1. Check if the response directly answers the question\n"
            "2. Verify the information is accurate\n"
            "3. Assess if the response is complete and helpful"
        ),
        reasoning=(
            "A good response should be accurate, complete, and directly address the user's "
            "question."
        ),
        possible_scores=["poor", "fair", "good", "perfect"],
        successful_scores=[
            "good",
            "perfect",
        ],  # Only "good" and "excellent" are considered successful
        evaluation_examples=(
            "Example: Question: 'What is Python?' "
            "Good response: 'Python is a programming language...' "
            "Poor response: 'I don't know.'"
        ),
        model="gemini",  # Optional: specify the model to use
    )

    # Example evaluation
    input_query = "What is machine learning?"
    system_output = (
        "Machine learning is a subset of artificial intelligence that enables computers to "
        "learn and improve from experience without being explicitly programmed."
    )
    expected_output = (
        "Machine learning is a field of AI that focuses on algorithms that can learn from data."
    )

    # Evaluate the response
    result = metric.evaluate(
        input=input_query,
        output=system_output,
        expected_output=expected_output,
        context=["AI and machine learning concepts", "Computer science fundamentals"],
    )

    print("\nEvaluation Result:")
    print(f"Score: {result.score}")
    print(f"Is Successful: {result.details['is_successful']}")
    print(f"Reason: {result.details['reason']}")
    print(f"Possible Scores: {result.details['possible_scores']}")
    print(f"Successful Scores: {result.details['successful_scores']}")
    print(f"Details: {result.details['prompt']}")
