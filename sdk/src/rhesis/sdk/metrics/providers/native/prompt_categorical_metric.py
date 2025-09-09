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

        # Pass successful_scores to the base class
        super().__init__(
            name=name,
            metric_type=metric_type,
            model=model,
        )

        # Store other parameters
        self.evaluation_prompt = evaluation_prompt
        self.evaluation_steps = evaluation_steps
        self.reasoning = reasoning
        self.evaluation_examples = evaluation_examples

        # Set up Jinja environment (cached for performance)
        self._setup_jinja_environment()

    def _validate_possible_scores(self) -> None:
        """Validate that possible_scores is a valid list with at least 2 scores."""
        if not isinstance(self.possible_scores, list) or len(self.possible_scores) < 2:
            raise ValueError(
                f"possible_scores must be a list with at least 2 scores, "
                f"got: {self.possible_scores}"
            )

    def _validate_successful_scores(self) -> None:
        """Validate that successful_scores is a string or list."""
        if not isinstance(self.successful_scores, (str, list)):
            raise ValueError(
                f"successful_scores must be a string or list, got: {type(self.successful_scores)}"
            )

    def _normalize_successful_scores(self) -> None:
        """Convert string successful_scores to list for consistent handling."""
        if isinstance(self.successful_scores, str):
            self.successful_scores = [self.successful_scores]

    def _validate_successful_scores_subset(self) -> None:
        """Validate that successful_scores is a subset of possible_scores."""
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
        """Set up Jinja environment for template rendering."""
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

    def get_prompt_template(
        self, input: str, output: str, expected_output: str, context: Optional[List[str]] = None
    ) -> str:
        """
        Generate the prompt to be sent to the LLM using a Jinja template.

        Args:
            input: The input query/question
            output: The system output/response
            expected_output: The expected or reference output
            context: List of context chunks used for the response

        Returns:
            str: The rendered prompt template

        Raises:
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

        Args:
            input: The input query/question
            output: The system output/response
            expected_output: The expected or reference output (ground truth)
            context: List of context chunks used for the response

        Returns:
            MetricResult: The evaluation result
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
        prompt = self.get_prompt_template(input, output, expected_output or "", context or [])

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
            is_successful = self.evaluate_score(
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

    def evaluate_score(self, score: str, successful_scores: List[str]) -> bool:
        """
        Evaluate if a score meets the success criteria based on score type and threshold operator.
        This method is implemented by the derived classes.
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
        model="rhesis",  # Optional: specify the model to use
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
    # print(f"Details: {result.details['prompt']}")
