from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.synthesizers.base import TestSetSynthesizer


class PromptSynthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a prompt using LLM."""

    def __init__(self, prompt: str, batch_size: int = 5, system_prompt: Optional[str] = None):
        """
        Initialize the PromptSynthesizer.

        Args:
            prompt: The generation prompt to use
            batch_size: Maximum number of tests to generate in a single LLM call
            system_prompt: Optional custom system prompt template to override the default
        """
        super().__init__(batch_size=batch_size)
        self.prompt = prompt

        if system_prompt:
            self.system_prompt = Template(system_prompt)
        else:
            # Load default system prompt from assets
            prompt_path = Path(__file__).parent / "assets" / "prompt_synthesizer.md"
            with open(prompt_path, "r") as f:
                self.system_prompt = Template(f.read())

    def _generate_batch(self, num_tests: int) -> List[Dict[str, Any]]:
        """Generate a batch of test cases."""
        formatted_prompt = self.system_prompt.render(
            generation_prompt=self.prompt, num_tests=num_tests
        )

        # Use run() method with default parameters
        response = self.llm_service.run(prompt=formatted_prompt)

        if not isinstance(response, dict) or "tests" not in response:
            raise ValueError(f"Expected a dict with 'tests' key, got {type(response).__name__}")

        test_cases = response["tests"]
        if not isinstance(test_cases, list):
            raise ValueError(f"Expected 'tests' to be a list, got {type(test_cases).__name__}")

        # Ensure we get the requested number of test cases
        if len(test_cases) < num_tests:
            for attempt in range(2):  # Try up to 2 more times
                additional_response = self.llm_service.run(prompt=formatted_prompt)
                if not isinstance(additional_response, dict) or "tests" not in additional_response:
                    continue
                additional_cases = additional_response["tests"]
                if not isinstance(additional_cases, list):
                    continue
                test_cases.extend(additional_cases)

                if len(test_cases) >= num_tests:
                    break

            if len(test_cases) < num_tests:
                raise ValueError(f"LLM returned {len(test_cases)} test cases, expected {num_tests}")

        # Take exactly num_tests results
        test_cases = test_cases[:num_tests]

        # Add metadata to each test case
        return [
            {
                **test,
                "metadata": {
                    "generated_by": "PromptSynthesizer",
                },
            }
            for test in test_cases
        ]

    def generate(self, **kwargs: Any) -> TestSet:
        """
        Generate test cases based on the given prompt.

        Args:
            **kwargs: Keyword arguments, supports:
                num_tests (int): Total number of test cases to generate. Defaults to 5.

        Returns:
            TestSet: A TestSet entity containing the generated test cases
        """
        num_tests = kwargs.get("num_tests", 5)
        if not isinstance(num_tests, int):
            raise TypeError("num_tests must be an integer")

        all_test_cases = []

        # Generate all tests in a single batch
        all_test_cases = self._generate_batch(num_tests)

        test_set = TestSet(
            tests=all_test_cases,
            metadata={
                "generation_prompt": self.prompt,
                "num_tests": num_tests,
                "batch_size": self.batch_size,
                "synthesizer": "PromptSynthesizer",
            },
        )

        # Set properties based on the generated tests
        test_set.set_properties()

        return test_set
