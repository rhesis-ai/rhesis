from pathlib import Path
from typing import List, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.providers.native.metric_base import (
    RhesisMetricBase,
    ScoreType,
)


class ScoreResponseCategorical(BaseModel):
    """Model for structured score response from LLM evaluation."""

    score: str = Field(description="Evaluation score")
    reason: str = Field(description="Explanation for the score", default="")


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
        evaluation_examples: str = "",
        successful_scores: Optional[Union[str, List[str]]] = None,
        model: Optional[str] = None,
        metric_type="rag",
        **kwargs,
    ):
        # Convert string to enum if needed

        self.score_type = ScoreType.CATEGORICAL
        self.model = model

        # Handle different score types
        if successful_scores is None:
            # if self.score_type == ScoreType.BINARY:
            #     reference_score = "true"  # Default reference for binary
            # else:  # CATEGORICAL
            raise ValueError("successful_scores is required for categorical score type")

        # Pass successful_scores to the base class, threshold is None
        super().__init__(
            name=name,
            successful_scores=successful_scores,
            metric_type=metric_type,
            model=model,
        )

        # Store other parameters
        self.evaluation_prompt = evaluation_prompt
        self.evaluation_steps = evaluation_steps
        self.reasoning = reasoning
        self.evaluation_examples = evaluation_examples

        # Set up Jinja environment
        templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
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
        self, input: str, output: str, expected_output: str, context: List[str] = None
    ) -> str:
        """
        Generate the prompt to be sent to the LLM using a Jinja template.
        """
        context_text = "\n".join(context) if context else "No context provided."

        # Load the template
        template = self.jinja_env.get_template("prompt_metric.jinja")

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
        }

        # Render the template with all required variables
        prompt = template.render(**template_vars)

        return prompt

    def _process_score(self, raw_score: str) -> str:
        """
        Process the raw score based on the score type.

        Args:
            raw_score: The raw score from the LLM

        Returns:
            Union[float, str]: Processed score
        """

        return raw_score

    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str] = None
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
        if expected_output is None and self.requires_ground_truth:
            raise ValueError(f"{self.name} metric requires ground truth but none was provided")

        # Generate the evaluation prompt
        prompt = self.get_prompt_template(input, output, expected_output or "", context or [])

        try:
            # Run the evaluation with structured response model
            response = self._model.generate(prompt, schema=ScoreResponseCategorical)
            response = ScoreResponseCategorical(**response)

            # Get the score and process it based on score type
            score = self._process_score(response.score)
            reason = response.reason

            # Check if the evaluation meets the reference score using the base class method
            is_successful = self.evaluate_score(
                score=score,
                score_type=self.score_type,
                successful_scores=self.successful_scores,
            )

            # Prepare details based on score type
            details = {
                "score": score,
                "score_type": self.score_type.value,
                "prompt": prompt,
                "reason": reason,
                "is_successful": is_successful,
                "successful_scores": self.successful_scores,
            }

            return MetricResult(score=score, details=details)

        except Exception as e:
            # Log the error for debugging with full traceback
            import logging
            import traceback

            logger = logging.getLogger(__name__)

            error_msg = f"Error evaluating with {self.name}: {str(e)}"
            logger.error(f"Exception in RhesisPromptMetric.evaluate: {error_msg}")
            logger.error(f"Provider: {self.provider}, Model: {self.model}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception details: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

            # Return a fallback score with error information
            details = {
                "error": error_msg,
                "reason": error_msg,
                "exception_type": type(e).__name__,
                "exception_details": str(e),
                "model": self.model,
                "prompt": prompt,
                "score_type": self.score_type.value,
                "successful_scores": self.successful_scores,
            }

            # Return a default failure score for binary/categorical
            return MetricResult(score="error", details=details)


if __name__ == "__main__":
    pass
