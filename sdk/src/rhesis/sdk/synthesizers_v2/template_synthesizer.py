from pathlib import Path
from typing import Any, List, Optional, Union

from jinja2 import Template

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.synthesizers_v2.base import BaseSynthesizer
from rhesis.sdk.synthesizers_v2.utils import (
    parse_llm_response,
    retry_llm_call,
)


class TemplateSynthesizer(BaseSynthesizer):
    """Template-based synthesizer for generating test sets using LLM and templates."""

    # Subclasses should override this to specify their template
    template_name: Optional[str] = None

    def __init__(
        self,
        batch_size: int = 5,
        model: Optional[Union[str, BaseLLM]] = None,
        max_attempts: int = 3,
    ):
        """
        Initialize the template synthesizer.

        Args:
            batch_size: Maximum number of items to process in a single LLM call
            model: LLM model to use (string name or BaseLLM instance)
            max_attempts: Maximum retry attempts for LLM calls
        """
        super().__init__(batch_size=batch_size)
        self.max_attempts = max_attempts

        # Initialize model
        if isinstance(model, str) or model is None:
            self.model = get_model(model)
        else:
            self.model = model

        # Load template using class variable
        if self.template_name:
            self.template = self.load_prompt_template(self.template_name)
        else:
            raise ValueError(
                "No template specified. Set template_name as a class variable "
                "in your synthesizer subclass."
            )

    @staticmethod
    def load_prompt_template(template_name: str) -> Template:
        """Load prompt template from assets directory."""
        # Convert camel case to snake case
        snake_case = "".join(
            ["_" + c.lower() if c.isupper() else c.lower() for c in template_name]
        ).lstrip("_")

        prompt_path = Path(__file__).parent / "assets" / f"{snake_case}.md"
        try:
            with open(prompt_path, "r") as f:
                return Template(f.read())
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Template file not found: {prompt_path}. "
                f"Please create the template file or check the template name."
            )

    def create_test_set(self, tests: List[dict], **metadata_kwargs) -> TestSet:
        """Create and configure a TestSet with metadata."""
        metadata = self._create_test_set_metadata({}, tests)
        metadata.update(metadata_kwargs)

        test_set = TestSet(tests=tests, metadata=metadata, model=self.model)
        test_set.set_properties()
        return test_set

    def generate(self, num_tests: int = 3, **template_vars: Any) -> TestSet:
        """Generate a test set using the template and LLM.

        This is the template method that orchestrates the generation flow.
        Subclasses can override the protected methods to customize behavior.
        """
        # Prepare template variables
        template_data = self._prepare_template_vars(num_tests, template_vars)

        # Render template
        rendered_prompt = self._render_template(template_data)

        # Execute LLM call
        response = self._execute_llm(rendered_prompt)

        # Parse response
        tests = self._parse_response(response)

        # Create metadata
        metadata = self._create_test_set_metadata(template_data, tests)

        # Create and return TestSet
        return self.create_test_set(tests=tests, **metadata)

    # Extension points that subclasses can override
    def _prepare_template_vars(self, num_tests: int, template_vars: dict) -> dict:
        """Prepare template variables. Subclasses can customize this."""
        return {"num_tests": num_tests, **template_vars}

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
