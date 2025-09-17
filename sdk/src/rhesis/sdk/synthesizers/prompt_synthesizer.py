"""A synthesizer that generates test cases based on a prompt using LLM."""

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Union

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.synthesizers.config_synthesizer import GenerationConfig
from rhesis.sdk.synthesizers.utils import (
    create_test_set,
    load_prompt_template,
    parse_llm_response,
    retry_llm_call,
)
from rhesis.sdk.utils import clean_and_validate_tests


class PromptSynthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a prompt using LLM."""

    def __init__(
        self,
        prompt: str,
        batch_size: int = 20,
        system_prompt: Optional[str] = None,
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        """
        Initialize the PromptSynthesizer.
        Args:
            prompt: The generation prompt to use
            batch_size: Maximum number of tests to generate in a single LLM call (reduced default
            for stability)
            system_prompt: Optional custom system prompt template to override the default
        """

        super().__init__(batch_size=batch_size)
        self.prompt = prompt

        # Set system prompt using utility function
        self.system_prompt = load_prompt_template(self.__class__.__name__, system_prompt)

        if isinstance(model, str) or model is None:
            self.model = get_model(model)
        else:
            self.model = model

    def _generate_batch(
        self,
        num_tests: int,
        context: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> List[Dict[str, Any]]:
        """Generate a batch of test cases with improved error handling."""

        config = asdict(config)
        formatted_prompt = self.system_prompt.render(
            generation_prompt=self.prompt, **config, num_tests=num_tests, context=context
        )

        # Use utility function for retry logic
        response = retry_llm_call(self.model, formatted_prompt)

        # Use utility function for response parsing
        test_cases = parse_llm_response(response, expected_keys=["tests"])

        # Clean and validate test cases using utility function
        valid_test_cases = clean_and_validate_tests(test_cases)

        if valid_test_cases:
            # Add metadata to each test case
            return [
                {
                    **test,
                    "metadata": {
                        "generated_by": "PromptSynthesizer",
                        "context_used": context is not None,
                        "context_length": len(context) if context else 0,
                    },
                }
                for test in valid_test_cases[:num_tests]
            ]

        return []

    def generate(
        self,
        num_tests: int = 5,
        context: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> TestSet:
        """
        Generate test cases based on the given prompt.

        Args:
            num_tests: Total number of test cases to generate. Defaults to 5.
            context: Optional context string to use for generation.

        Returns:
            TestSet: A TestSet entity containing the generated test cases
        """
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
                    chunk_tests = self._generate_batch(chunk_size, context, config)
                    all_test_cases.extend(chunk_tests)
                    remaining_tests -= len(chunk_tests)

                    # If we didn't get the expected number, try again with a smaller chunk
                    if len(chunk_tests) < chunk_size and chunk_size > 5:
                        remaining_tests += chunk_size - len(chunk_tests)
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
            all_test_cases = self._generate_batch(num_tests, context, config)

        # Ensure we have some test cases
        if not all_test_cases:
            raise ValueError("Failed to generate any valid test cases")

        # Use utility function to create TestSet
        return create_test_set(
            all_test_cases,
            model=self.model,
            synthesizer_name="PromptSynthesizer",
            batch_size=self.batch_size,
            generation_prompt=self.prompt,
            num_tests=len(all_test_cases),
            requested_tests=num_tests,
            context_used=context is not None,
            context_length=len(context) if context else 0,
        )
