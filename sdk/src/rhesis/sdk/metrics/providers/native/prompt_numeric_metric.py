from pathlib import Path
from typing import List, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.providers.native.metric_base import (
    RhesisMetricBase,
    ScoreType,
    ThresholdOperator,
)


class NumericScoreResponse(BaseModel):
    """Model for structured numeric response from LLM evaluation."""

    score: float = Field(description="Evaluation score")
    reason: str = Field(description="Explanation for the score", default="")


class RhesisPromptMetricNumeric(RhesisMetricBase):
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
        threshold_operator: Union[ThresholdOperator, str] = None,
        model: Optional[str] = None,
        metric_type="rag",
        **kwargs,
    ):
        # Convert string to enum if needed
        if isinstance(threshold_operator, str):
            threshold_operator = ThresholdOperator(threshold_operator)

        self.score_type = ScoreType.NUMERIC
        self.threshold_operator = threshold_operator
        self.model = model

        if min_score is not None and max_score is None:
            raise ValueError("Only min_score was set, please set max_score")

        if min_score is None and max_score is not None:
            raise ValueError("Only max_score was set, please set min_score")

        # For numeric scores, we need min_score, max_score, and threshold
        self.min_score = min_score if min_score is not None else 0
        self.max_score = max_score if max_score is not None else 1

        if threshold is None:
            self.threshold = self.min_score + (self.max_score - self.min_score) / 2
        else:
            self.threshold = threshold

        if not (self.min_score <= self.threshold <= self.max_score):
            raise ValueError(f"Threshold must be between {self.min_score} and {self.max_score}")

        # Pass the normalized threshold to the base class
        super().__init__(
            name=name,
            threshold=self.threshold,
            reference_score=None,
            metric_type=metric_type,
            model=model,
            **kwargs,
        )

        # Store other parameters
        self.evaluation_prompt = evaluation_prompt
        self.evaluation_steps = evaluation_steps
        self.reasoning = reasoning
        self.evaluation_examples = evaluation_examples

        # Set up Jinja environment
        templates_dir = Path(__file__).resolve().parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
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

        # Prepare template variables for numeric scoring
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
            "min_score": self.min_score,
            "max_score": self.max_score,
        }

        # Render the template with all required variables
        prompt = template.render(**template_vars)

        return prompt

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
            response = self._model.generate(prompt, schema=NumericScoreResponse)
            response = NumericScoreResponse(**response)

            # Get the score directly from the response
            score = response.score
            reason = response.reason

            # Check if the evaluation meets the threshold using the base class method
            is_successful = self.evaluate_score(
                score=score,
                score_type=self.score_type,
                threshold=self.threshold,
                threshold_operator=self.threshold_operator,
            )

            # Prepare details based on score type
            details = {
                "score": score,
                "score_type": self.score_type.value,
                "prompt": prompt,
                "reason": reason,
                "is_successful": is_successful,
                "threshold_operator": (
                    self.threshold_operator.value if self.threshold_operator else None
                ),
                "min_score": self.min_score,
                "max_score": self.max_score,
                "threshold": self.threshold,
            }

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

            # Return a fallback score with error information
            details = {
                "error": error_msg,
                "reason": error_msg,
                "exception_type": type(e).__name__,
                "exception_details": str(e),
                "model": self.model,
                "prompt": prompt,
                "score_type": self.score_type.value,
                "threshold_operator": (
                    self.threshold_operator.value if self.threshold_operator else None
                ),
                "min_score": self.min_score,
                "max_score": self.max_score,
                "threshold": self.threshold,
            }

            # Return a default minimal score for numeric
            return MetricResult(score=0.0, details=details)


if __name__ == "__main__":
    metric = RhesisPromptMetricNumeric(
        name="test",
        evaluation_prompt="",
        evaluation_steps="",
        reasoning="",
    )
    input = "What is the capital of France?"
    output = ""
    expected_output = "Paris is the capital of France."
    context = [
        "Paris is the capital and largest city of France.",
        "Known as the City of Light, Paris is a global center for art, culture, and fashion.",
    ]
    metric_result = metric.evaluate(input, output, expected_output, context)
    from pprint import pprint

    pprint(metric_result)
    print(metric_result)
    print("finished")
