from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel
from tqdm.auto import tqdm

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models import get_model
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.synthesizers.utils import (
    load_prompt_template,
)


class Prompt(BaseModel):
    content: str
    expected_response: str
    language_code: str


class Test(BaseModel):
    prompt: Prompt
    behavior: str
    category: str
    topic: str


class Tests(BaseModel):
    tests: List[Test]


class TestSetSynthesizer(ABC):
    """Base class for all test set synthesizers."""

    prompt_template_file: str

    def __init__(self, batch_size: int = 5, model: Optional[Union[str, BaseLLM]] = None):
        """
        Initialize the base synthesizer.

        Args:
            batch_size: Maximum number of items to process in a single LLM call
        """
        self.batch_size = batch_size
        self.prompt_template = load_prompt_template(self.prompt_template_file)

        if isinstance(model, str) or model is None:
            self.model = get_model(model)
        else:
            self.model = model

    def _process_with_progress(
        self,
        items: List[Any],
        process_func: Any,
        desc: str = "Processing",
    ) -> List[Any]:
        """Process items with a progress bar."""
        results = []
        with tqdm(total=len(items), desc=desc) as pbar:
            for item in items:
                result = process_func(item)
                if isinstance(result, list):
                    results.extend(result)
                else:
                    results.append(result)
                pbar.update(1)
        return results

    @abstractmethod
    def _get_template_context(self, **generate_kwargs: Any) -> Dict[str, Any]:
        """
        Prepare template context for _generate_batch() call.

        Subclasses should combine instance attributes (from __init__)
        with runtime parameters (from generate()) to build the template context.

        Args:
            **generate_kwargs: Runtime parameters passed to generate()

        Returns:
            Dict containing template context to pass to _generate_batch()
        """
        pass

    def _get_synthesizer_name(self) -> str:
        """
        Return the name of the synthesizer for metadata.

        By default, returns the class name. Subclasses can override
        if they need a custom name.

        Returns:
            str: The synthesizer name (e.g., "SimpleSynthesizer")
        """
        return self.__class__.__name__

    def generate(self, num_tests: int = 5, **kwargs: Any) -> TestSet:
        """
        Generate test cases with automatic chunking.

        Args:
            num_tests: Total number of test cases to generate. Defaults to 5.
            **kwargs: Additional keyword arguments for test set generation

        Returns:
            TestSet: A TestSet entity containing the generated test cases
        """
        from rhesis.sdk.synthesizers.utils import create_test_set

        if not isinstance(num_tests, int):
            raise TypeError("num_tests must be an integer")

        all_test_cases = []
        template_context = self._get_template_context(**kwargs)

        # For large numbers, use chunking to avoid JSON parsing issues
        if num_tests > self.batch_size:
            # Generate in chunks
            remaining_tests = num_tests
            while remaining_tests > 0:
                chunk_size = min(self.batch_size, remaining_tests)
                try:
                    chunk_tests = self._generate_batch(chunk_size, **template_context)
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
            all_test_cases = self._generate_batch(num_tests, **template_context)

        # Ensure we have some test cases
        if not all_test_cases:
            raise ValueError("Failed to generate any valid test cases")

        # Use utility function to create TestSet
        return create_test_set(
            all_test_cases,
            model=self.model,
            synthesizer_name=self._get_synthesizer_name(),
            batch_size=self.batch_size,
            num_tests=len(all_test_cases),
            requested_tests=num_tests,
            **kwargs,
        )

    def _generate_batch(
        self,
        num_tests: int,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Generate a batch of test cases with improved error handling."""
        template_context = {"num_tests": num_tests, **kwargs}
        prompt = self.prompt_template.render(**template_context)

        # Use utility function for retry logic
        response = self.model.generate(prompt=prompt, schema=Tests)
        tests = response["tests"][:num_tests]

        tests = [
            {
                **test,
                "metadata": {
                    "generated_by": self._get_synthesizer_name(),
                },
            }
            for test in tests
        ]

        return tests


if __name__ == "__main__":
    template = load_prompt_template("simple_synthesizer.md")
    print(template.render(num_tests=5))
