from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.utils import extract_json_from_text, clean_and_validate_tests


class PromptSynthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a prompt using LLM."""

    def __init__(self, prompt: str, batch_size: int = 20, system_prompt: Optional[str] = None):
        """
        Initialize the PromptSynthesizer.

        Args:
            prompt: The generation prompt to use
            batch_size: Maximum number of tests to generate in a single LLM call (reduced default for stability)
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
        """Generate a batch of test cases with improved error handling."""
        formatted_prompt = self.system_prompt.render(
            generation_prompt=self.prompt, num_tests=num_tests
        )

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Use run() method with default parameters
                response = self.llm_service.run(prompt=formatted_prompt)
                
                # Handle different response types
                if isinstance(response, dict) and "tests" in response:
                    test_cases = response["tests"]
                elif isinstance(response, str):
                    # Use utility function for robust JSON extraction
                    parsed_response = extract_json_from_text(response)
                    test_cases = parsed_response.get("tests", [])
                else:
                    raise ValueError(f"Unexpected response type: {type(response)}")

                # Clean and validate test cases using utility function
                valid_test_cases = clean_and_validate_tests(test_cases)

                if valid_test_cases:
                    # Add metadata to each test case
                    return [
                        {
                            **test,
                            "metadata": {
                                "generated_by": "PromptSynthesizer",
                                "attempt": attempt + 1,
                            },
                        }
                        for test in valid_test_cases[:num_tests]
                    ]

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_attempts - 1:
                    raise ValueError(f"Failed to generate test cases after {max_attempts} attempts: {e}")

        return []

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

        # For large numbers, use chunking to avoid JSON parsing issues
        if num_tests > self.batch_size:
            # Generate in chunks
            remaining_tests = num_tests
            while remaining_tests > 0:
                chunk_size = min(self.batch_size, remaining_tests)
                try:
                    chunk_tests = self._generate_batch(chunk_size)
                    all_test_cases.extend(chunk_tests)
                    remaining_tests -= len(chunk_tests)
                    
                    # If we didn't get the expected number, try again with a smaller chunk
                    if len(chunk_tests) < chunk_size and chunk_size > 5:
                        remaining_tests += (chunk_size - len(chunk_tests))
                        self.batch_size = max(5, self.batch_size // 2)
                        
                except Exception as e:
                    print(f"Error generating chunk of {chunk_size} tests: {e}")
                    # Try with smaller batch size
                    if self.batch_size > 5:
                        self.batch_size = max(5, self.batch_size // 2)
                        continue
                    else:
                        break
        else:
            # Generate all tests in a single batch
            all_test_cases = self._generate_batch(num_tests)

        # Ensure we have some test cases
        if not all_test_cases:
            raise ValueError("Failed to generate any valid test cases")

        test_set = TestSet(
            tests=all_test_cases,
            metadata={
                "generation_prompt": self.prompt,
                "num_tests": len(all_test_cases),
                "requested_tests": num_tests,
                "batch_size": self.batch_size,
                "synthesizer": "PromptSynthesizer",
            },
        )

        # Set properties based on the generated tests
        test_set.set_properties()

        return test_set
