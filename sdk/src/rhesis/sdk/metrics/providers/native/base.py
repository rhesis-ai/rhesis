from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union

from rhesis.sdk.metrics.base import BaseMetric, MetricResult
from rhesis.sdk.metrics.providers.native.configs import BaseJudgeConfig
from rhesis.sdk.metrics.providers.native.serialization import BackendSyncMixin, SerializationMixin
from rhesis.sdk.metrics.providers.native.shared_utils import (
    get_base_details,
    handle_evaluation_error,
    setup_jinja_environment,
)
from rhesis.sdk.models import BaseLLM

# Type variable for generic return types
T = TypeVar("T", bound="JudgeBase")


class JudgeBase(BaseMetric, SerializationMixin, BackendSyncMixin):
    """
    A generic metric that evaluates outputs based on a custom prompt template.
    Uses LLM to perform evaluation based on provided evaluation criteria.
    """

    def __init__(self, config: BaseJudgeConfig, model: Optional[Union[BaseLLM, str]] = None):
        self.config = config
        super().__init__(config=self.config, model=model)
        self.evaluation_prompt = self.config.evaluation_prompt
        self.evaluation_steps = self.config.evaluation_steps
        self.reasoning = self.config.reasoning
        self.evaluation_examples = self.config.evaluation_examples

    def evaluate(self, *args, **kwargs) -> MetricResult:
        raise NotImplementedError("Subclasses should override this method")

    def _validate_evaluate_inputs(
        self,
        input: str,
        output: str,
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
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

        if expected_output is None and self.requires_ground_truth is True:
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
        return get_base_details(self.score_type, prompt)

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

        if self.score_type is None:
            raise ValueError("score_type must be set before calling _get_prompt_template")

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
