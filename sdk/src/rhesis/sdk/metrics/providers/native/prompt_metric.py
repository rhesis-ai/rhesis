import logging
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricResult, MetricType, ScoreType
from rhesis.sdk.models.base import BaseLLM


class RhesisPromptMetricBase(BaseMetric):
    """
    A generic metric that evaluates outputs based on a custom prompt template.
    Uses LLM to perform evaluation based on provided evaluation criteria.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        score_type: Optional[Union[str, ScoreType]] = None,
        metric_type: Optional[Union[str, MetricType]] = None,
        model: Optional[Union[BaseLLM, str]] = None,
        **kwargs,
    ):
        super().__init__(
            name=name,
            description=description,
            score_type=score_type,
            metric_type=metric_type,
            model=model,
            **kwargs,
        )

    def _validate_evaluate_inputs(
        self, input: str, output: str, expected_output: Optional[str], context: Optional[List[str]]
    ) -> None:
        """
        Validate common inputs for evaluate method.

        Args:
            input (str): The input query/question
            output (str): The system output/response
            expected_output (Optional[str]): The expected or reference output
            context (Optional[List[str]]): List of context chunks

        Raises:
            ValueError: If any input validation fails
        """
        if not isinstance(input, str) or not input.strip():
            raise ValueError("input must be a non-empty string")

        if not isinstance(output, str):
            raise ValueError("output must be a string")

        if expected_output is None and self.requires_ground_truth:
            raise ValueError(f"{self.name} metric requires ground truth but none was provided")

        if context is not None and not isinstance(context, list):
            raise ValueError("context must be a list of strings or None")

    def _get_base_details(self, prompt: str) -> Dict[str, Any]:
        """
        Get base details dictionary common to all metric types.

        Args:
            prompt (str): The evaluation prompt

        Returns:
            Dict[str, Any]: Base details dictionary
        """
        return {
            "score_type": self.score_type.value,
            "prompt": prompt,
        }

    def _handle_evaluation_error(
        self, e: Exception, details: Dict[str, Any], default_score: Any
    ) -> MetricResult:
        """
        Handle evaluation errors with consistent logging and error details.

        Args:
            e (Exception): The exception that occurred
            details (Dict[str, Any]): Details dictionary to update
            default_score (Any): Default score to return on error

        Returns:
            MetricResult: Error result with default score
        """
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
                "is_successful": False,
            }
        )

        return MetricResult(score=default_score, details=details)

    def _setup_jinja_environment(self) -> None:
        """
        Set up Jinja environment for template rendering.

        This method initializes a Jinja2 environment with the templates directory
        and configures it for optimal template rendering performance.
        """
        templates_dir = Path(__file__).resolve().parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

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

        This method renders the Jinja2 template with all necessary variables to create
        a comprehensive evaluation prompt for the LLM.

        Args:
            input (str): The input query/question
            output (str): The system output/response
            expected_output (str): The expected or reference output
            context (Optional[List[str]], optional): List of context chunks used for the response.
                Defaults to None.
            **additional_template_vars: Additional template variables specific to the metric type

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

        # Prepare base template variables
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

        # Add any additional template variables specific to the metric type
        template_vars.update(additional_template_vars)

        try:
            # Render the template with all required variables
            prompt = template.render(**template_vars)
        except Exception as e:
            raise ValueError(f"Failed to render template: {e}") from e

        return prompt

    def to_config(self) -> MetricConfig:
        """Convert the metric to a MetricConfig."""
        """Subclasses should override this method to add their own parameters."""
        config = MetricConfig(
            # Backend required items
            class_name=self.__class__.__name__,
            backend="rhesis",
            name=self.name,
            description=self.description,
            score_type=self.score_type,
            metric_type=self.metric_type,
            ground_truth_required=self.ground_truth_required,
            context_required=self.context_required,
            # Custom parameters
            evaluation_prompt=self.evaluation_prompt,
            evaluation_steps=self.evaluation_steps,
            reasoning=self.reasoning,
            evaluation_examples=self.evaluation_examples,
            parameters={},
        )

        return config
