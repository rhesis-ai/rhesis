from typing import Any, Optional, Union

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

        Args:
            num_items: Number of items to generate
            **template_vars: Template variables for rendering

        Returns:
            TestSet: A TestSet entity containing the generated test cases
        """
        # Prepare template variables
        template_data = {"num_items": num_items, **template_vars}

        # Render the template
        rendered_prompt = self.template.render(**template_data)

        # Execute LLM call with retry
        response = retry_llm_call(self.model, rendered_prompt, self.max_attempts)

        # Parse the response into structured data
        tests = parse_llm_response(response)

        # Create and return TestSet
        return create_test_set(
            tests=tests,
            model=self.model,
            synthesizer_name=self.__class__.__name__,
            batch_size=self.batch_size,
            template_name=self.template_name,
            rendered_prompt=rendered_prompt,
            template_vars=template_vars,
        )


# Example usage
if __name__ == "__main__":
    # Example 1: Using a custom template
    custom_template = """
    You are a helpful assistant. Generate {{ num_items }} test cases for the following task:

    Task: {{ task_description }}

    Additional context: {{ context }}
    Domain: {{ domain }}

    Please return the test cases in JSON format with the following structure:
    {
        "tests": [
            {
                "input": "test input",
                "expected_output": "expected output",
                "description": "what this test validates"
            }
        ]
    }
    """

    synthesizer = TemplateSynthesizer(
        custom_template=custom_template,
        batch_size=3,
        model="gemini",  # or any supported model
        max_attempts=2,
    )

    # Generate test cases
    test_set = synthesizer.generate(
        num_items=2,
        task_description="Create a function that validates email addresses",
        context="Focus on edge cases and common validation patterns",
        domain="email validation",
    )

    print("Generated Test Set:")
    print(f"Number of tests: {len(test_set.tests)}")
    print(f"Model used: {test_set.model}")
    print(f"Synthesizer: {test_set.metadata.get('synthesizer')}")

    # Print first test case
    if test_set.tests:
        print("\nFirst test case:")
        print(test_set.tests[0])
