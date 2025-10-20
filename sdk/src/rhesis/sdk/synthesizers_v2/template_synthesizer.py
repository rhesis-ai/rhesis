from typing import Any, List, Optional, Union

from jinja2 import Template

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.synthesizers_v2.base import BaseSynthesizer
from rhesis.sdk.synthesizers_v2.utils import (
    create_test_set,
    load_prompt_template,
    parse_llm_response,
    retry_llm_call,
)


class TemplateSynthesizer(BaseSynthesizer):
    """Template-based synthesizer for generating test sets using LLM and templates."""

    def __init__(
        self,
        template_name: Optional[str] = None,
        custom_template: Optional[str] = None,
        batch_size: int = 5,
        model: Optional[Union[str, BaseLLM]] = None,
        max_attempts: int = 3,
    ):
        """
        Initialize the template synthesizer.

        Args:
            template_name: Name of the template file to load from assets
            custom_template: Custom template string to use instead of loading from file
            batch_size: Maximum number of items to process in a single LLM call
            model: LLM model to use (string name or BaseLLM instance)
            max_attempts: Maximum retry attempts for LLM calls
        """
        super().__init__(batch_size=batch_size)
        self.max_attempts = max_attempts
        self.template_name = template_name

        # Initialize model
        if isinstance(model, str) or model is None:
            self.model = get_model(model)
        else:
            self.model = model

        # Load template
        if custom_template:
            self.template = Template(custom_template)
        elif template_name:
            self.template = load_prompt_template(template_name)
        else:
            self.template = Template(
                "Generate {{ num_items }} items based on the provided variables."
            )

    def generate(self, num_items: int = 3, **template_vars: Any) -> TestSet:
        """Generate a test set using the template and LLM.

        This is the template method that orchestrates the generation flow.
        Subclasses can override the protected methods to customize behavior.
        """
        # Prepare template variables
        template_data = self._prepare_template_vars(num_items, template_vars)

        # Render template
        rendered_prompt = self._render_template(template_data)

        # Execute LLM call
        response = self._execute_llm(rendered_prompt)

        # Parse response
        tests = self._parse_response(response)

        # Create metadata
        metadata = self._create_test_set_metadata(template_data, tests)

        # Create and return TestSet
        return create_test_set(tests=tests, model=self.model, **metadata)

    # Extension points that subclasses can override
    def _prepare_template_vars(self, num_items: int, template_vars: dict) -> dict:
        """Prepare template variables. Subclasses can customize this."""
        return {"num_items": num_items, **template_vars}

    def _render_template(self, template_data: dict) -> str:
        """Render the template. Subclasses can customize this."""
        return self.template.render(**template_data)

    def _execute_llm(self, rendered_prompt: str) -> Any:
        """Execute LLM call with retry. Subclasses can customize this."""
        return retry_llm_call(self.model, rendered_prompt, self.max_attempts)

    def _parse_response(self, response: Any) -> List[dict]:
        """Parse response into structured data. Subclasses can customize this."""
        return parse_llm_response(response)

    def _create_test_set_metadata(self, template_data: dict, tests: List[dict]) -> dict:
        """Create metadata for TestSet. Subclasses can customize this."""
        return {
            "synthesizer_name": self.__class__.__name__,
            "batch_size": self.batch_size,
            "template_name": self.template_name,
            "template_vars": template_data,
        }
