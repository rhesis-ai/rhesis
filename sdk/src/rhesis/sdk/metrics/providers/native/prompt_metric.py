import inspect
import logging
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from rhesis.sdk.client import Client, Endpoints, Methods
from rhesis.sdk.metrics.base import BaseMetric, MetricConfig, MetricResult
from rhesis.sdk.metrics.utils import backend_config_to_sdk_config, sdk_config_to_backend_config
from rhesis.sdk.models import BaseLLM

# Type variable for generic return types
T = TypeVar("T", bound="RhesisPromptMetricBase")

# Custom parameters


@dataclass
class PromptMetricConfig(MetricConfig):
    evaluation_prompt: Optional[str] = None
    evaluation_steps: Optional[str] = None
    reasoning: Optional[str] = None
    evaluation_examples: Optional[str] = None

    def __post_init__(self):
        return super().__post_init__()


class RhesisPromptMetricBase(BaseMetric):
    """
    A generic metric that evaluates outputs based on a custom prompt template.
    Uses LLM to perform evaluation based on provided evaluation criteria.
    """

    def __init__(self, config: PromptMetricConfig, model: Optional[Union[BaseLLM, str]] = None):
        self.config = config
        super().__init__(config=self.config, model=model)
        self.evaluation_prompt = self.config.evaluation_prompt
        self.evaluation_steps = self.config.evaluation_steps
        self.reasoning = self.config.reasoning
        self.evaluation_examples = self.config.evaluation_examples

    def __repr__(self) -> str:
        return str(self.to_config())

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
        if self.score_type is None:
            raise ValueError("score_type must be set before calling _get_base_details")
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

    def to_config(self) -> MetricConfig:
        """Convert the metric to a MetricConfig."""
        """Subclasses should override this method to add their own parameters."""
        return self.config

    @classmethod
    def from_config(cls: type[T], config: MetricConfig) -> T:
        """Create a metric from a config object."""
        # Get __init__ parameter names automatically
        init_params = inspect.signature(cls.__init__).parameters
        config_dict = asdict(config)

        # Only pass parameters that __init__ accepts
        filtered_params = {k: v for k, v in config_dict.items() if k in init_params}

        return cls(**filtered_params)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the metric to a dictionary."""
        return asdict(self.to_config())

    @classmethod
    def from_dict(cls: type[T], config: Dict[str, Any]) -> T:
        """Create a metric from a dictionary."""
        raise NotImplementedError("Subclasses should override this method")

    def push(self) -> None:
        """Push the metric to the backend."""
        client = Client()
        config = asdict(self.to_config())
        config = sdk_config_to_backend_config(config)

        client.send_request(Endpoints.METRICS, Methods.POST, config)

    @classmethod
    def pull(
        cls, name: Optional[str] = None, nano_id: Optional[str] = None
    ) -> "RhesisPromptMetricBase":
        """
        Pull the metric from the backend.
        # Either 'name' or 'nano_id' must be provided to pull a metric from the backend.
        # If 'name' is not unique (i.e., multiple metrics share the same name), an error
        # will be raised and you will be asked to use 'nano_id' instead for disambiguation.

        Args:
            name (Optional[str]): The name of the metric
            nano_id (Optional[str]): The nano_id of the metric

        Returns:
            RhesisPromptMetricNumeric: The metric
        """
        if not name and not nano_id:
            raise ValueError("Either name or nano_id must be provided")

        client = Client()

        # Build filter based on provided parameter
        filter_field = "nano_id" if nano_id else "name"
        filter_value = nano_id or name

        config = client.send_request(
            Endpoints.METRICS,
            Methods.GET,
            params={"$filter": f"{filter_field} eq '{filter_value}'"},
        )

        if not config:
            raise ValueError(f"No metric found with {filter_field} {filter_value}")

        if len(config) > 1:
            raise ValueError(f"Multiple metrics found with name {name}, please use nano_id")

        config = config[0]
        if config["class_name"] != cls.__name__:
            raise ValueError(f"Metric {config.get('id')} is not a {cls.__name__}")

        config = backend_config_to_sdk_config(config)
        return cls.from_dict(config)
