"""A synthesizer that generates test cases based on a prompt using LLM."""

from dataclasses import asdict
from typing import Any, List, Optional, Union

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.config_synthesizer import GenerationConfig
from rhesis.sdk.synthesizers_v2.template_synthesizer import TemplateSynthesizer


class PromptSynthesizer(TemplateSynthesizer):
    """Prompt-driven synthesizer built on TemplateSynthesizer base class.

    This class binds a user-provided prompt ("generation_prompt") to the
    default prompt_synthesizer template and delegates all rendering and LLM
    execution to the TemplateSynthesizer base class.
    """

    def __init__(
        self,
        prompt: str,
        batch_size: int = 20,
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        """Initialize the PromptSynthesizer.

        Args:
            prompt: The generation prompt to use
            batch_size: Maximum number of tests to generate in a single LLM call
            model: LLM model to use (string name or BaseLLM instance)
        """
        self.prompt = prompt

        # Always use the default asset template for prompt synthesizer
        super().__init__(
            template_name="prompt_synthesizer",
            template_string=None,
            batch_size=batch_size,
            model=model,
        )

    def _prepare_template_vars(self, num_tests: int, template_vars: dict) -> dict:
        """Add the prompt as generation_prompt variable."""
        return {"num_tests": num_tests, "generation_prompt": self.prompt, **template_vars}

    def _create_test_set_metadata(self, template_data: dict, tests: List[dict]) -> dict:
        """Add prompt-specific metadata."""
        metadata = super()._create_test_set_metadata(template_data, tests)
        metadata["generation_prompt"] = self.prompt
        return metadata

    def generate(
        self,
        num_tests: int = 5,
        context: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        **extra_vars: Any,
    ) -> TestSet:
        """Generate test cases based on the stored prompt.

        Args:
            num_tests: Total number of test cases to generate
            context: Optional context string for generation
            config: Optional GenerationConfig to expand the template variables
            **extra_vars: Additional template variables to pass through

        Returns:
            TestSet: Generated test set
        """
        if not isinstance(num_tests, int):
            raise TypeError("num_tests must be an integer")

        # Prepare template variables
        template_vars = {"context": context}
        if config is not None:
            template_vars.update(asdict(config))
        template_vars.update(extra_vars)

        # Delegate to base class
        return super().generate(num_tests=num_tests, **template_vars)


# Example usage
if __name__ == "__main__":
    # Example 1: Using the default prompt synthesizer template
    synthesizer = PromptSynthesizer(
        prompt="Create a function that validates email addresses",
        batch_size=3,
        model="gemini",  # or any supported model
    )

    # Generate test cases
    test_set = synthesizer.generate(
        num_tests=2,
        context="Focus on edge cases and common validation patterns",
    )

    print("Generated Test Set:")
    print(f"Number of tests: {len(test_set.tests)}")
    print(f"Model used: {test_set.model}")
    print(f"Synthesizer: {test_set.metadata.get('synthesizer')}")
    print(f"Prompt: {test_set.metadata.get('generation_prompt')}")

    # Print first test case
    if test_set.tests:
        print("\nFirst test case:")
        print(test_set.tests[0])

    # Example 2: Using a custom template
    custom_template = """
    You are a helpful assistant. Generate {{ num_items }} test cases for the following prompt:

    Prompt: {{ generation_prompt }}

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

    custom_synthesizer = PromptSynthesizer(
        prompt="Create a function that validates email addresses",
        batch_size=3,
        model="gemini",
    )

    # Generate test cases with custom template
    custom_test_set = custom_synthesizer.generate(
        num_tests=2,
        context="Focus on edge cases and common validation patterns",
        domain="email validation",
    )

    print("\nCustom Template Test Set:")
    print(f"Number of tests: {len(custom_test_set.tests)}")
    print(f"Template used: {custom_test_set.metadata.get('template_name')}")
