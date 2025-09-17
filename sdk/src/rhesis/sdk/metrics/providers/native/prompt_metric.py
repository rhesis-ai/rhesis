from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from rhesis.sdk.metrics.base import MetricConfig
from rhesis.sdk.metrics.providers.native.metric_base import (
    RhesisMetricBase,
)


class RhesisPromptMetricBase(RhesisMetricBase):
    """
    A generic metric that evaluates outputs based on a custom prompt template.
    Uses LLM to perform evaluation based on provided evaluation criteria.
    """

    def __init__(
        self,
        name: str,
        metric_type: str,
        model: str,
        **kwargs,
    ):
        super().__init__(
            name=name,
            metric_type=metric_type,
            model=model,
            **kwargs,
        )

        self.ground_truth_required = True
        self.context_required = False

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
        """Convert the metric to a dictionary."""
        """Subclasses should override this method to add their own parameters."""
        config = MetricConfig(
            class_name=self.__class__.__name__,
            backend="native",
            evaluation_prompt=self.evaluation_prompt,
            evaluation_steps=self.evaluation_steps,
            reasoning=self.reasoning,
            evaluation_examples=self.evaluation_examples,
            score_type=self.score_type,
            ground_truth_required=self.ground_truth_required,
            context_required=self.context_required,
            name=self.name,
            description=self.description,
            parameters={},
        )

        return config
