from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

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

    @property
    def requires_ground_truth(self) -> bool:
        """This metric typically requires ground truth."""
        return True
