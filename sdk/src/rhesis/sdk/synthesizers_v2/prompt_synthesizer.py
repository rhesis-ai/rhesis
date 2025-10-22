"""A synthesizer that generates test cases based on a prompt using LLM."""

from typing import Any, List, Optional, Union

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers_v2.template_synthesizer import TemplateSynthesizer


class PromptSynthesizer(TemplateSynthesizer):
    """Prompt-driven synthesizer built on TemplateSynthesizer base class.

    This class binds a user-provided prompt ("generation_prompt") to the
    default prompt_synthesizer template and delegates all rendering and LLM
    execution to the TemplateSynthesizer base class.
    """

    template_name = "prompt_synthesizer"

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
        **template_vars: Any,
    ) -> TestSet:
        """Generate test cases based on the stored prompt.

        Args:
            num_tests: Total number of test cases to generate
            **template_vars: Additional template variables to pass through

        Returns:
            TestSet: Generated test set
        """
        if not isinstance(num_tests, int):
            raise TypeError("num_tests must be an integer")

        # Delegate to base class
        return super().generate(num_tests=num_tests, **template_vars)


# Example usage
if __name__ == "__main__":
    # Create synthesizer
    synthesizer = PromptSynthesizer(
        prompt="Create a function that validates email addresses",
        batch_size=3,
        model="gemini",
    )

    # Generate test cases with template variables
    test_set = synthesizer.generate(
        num_tests=2,
        project_context="This is for a web application",
        test_purposes="Focus on edge cases and security",
        context="Test malformed emails and injection attempts",
    )

    print("Generated Test Set:")
    print(f"Number of tests: {len(test_set.tests)}")
    print(f"Model used: {test_set.model}")
    print(f"Synthesizer: {test_set.metadata.get('synthesizer_name')}")
    print(f"Template: {test_set.metadata.get('template_name')}")
    print(f"Prompt: {test_set.metadata.get('generation_prompt')}")

    # Print first test case
    if test_set.tests:
        print("\nFirst test case:")
        print(test_set.tests[0])
    else:
        print("No tests generated")
