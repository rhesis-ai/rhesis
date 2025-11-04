from typing import Any, Dict, List, Optional, Union

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.synthesizers.utils import (
    create_test_set,
    load_prompt_template,
)


class ParaphrasingSynthesizer(TestSetSynthesizer):
    """A synthesizer that generates paraphrased versions of existing test cases."""

    def __init__(
        self,
        test_set: TestSet,
        batch_size: int = 5,
        system_prompt: Optional[str] = None,
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        """
        Initialize the ParaphrasingSynthesizer.
        Args:
            test_set: The original test set to paraphrase
            batch_size: Maximum number of prompts to process in a single LLM call
            system_prompt: Optional custom system prompt template to override the default
            model: The model to use for generation (e.g., "gemini", "openai")
        """
        super().__init__(batch_size=batch_size)
        self.test_set = test_set
        self.num_paraphrases: int = 2  # Default value, can be overridden in generate()

        # Set system prompt using utility
        self.system_prompt = load_prompt_template(self.__class__.__name__, system_prompt)

        # Initialize model
        if isinstance(model, str) or model is None:
            self.model = get_model(model)
        else:
            self.model = model

    def _parse_paraphrases(self, content: Any) -> List[Dict[str, Any]]:
        """
        Parse the LLM response content into a list of paraphrased versions.

        Args:
            content: Python object from LLM containing paraphrased prompts

        Returns:
            List of dictionaries with formatted prompt structure

        Raises:
            ValueError: If the response is not in the expected format (object with tests array)
        """
        if not isinstance(content, dict):
            raise ValueError(f"Expected a dict, got {type(content).__name__}")

        if "tests" not in content:
            raise ValueError("Response missing 'tests' key")

        tests = content["tests"]
        if not isinstance(tests, list):
            raise ValueError(f"Expected 'tests' to be a list, got {type(tests).__name__}")

        paraphrases = []
        for i, item in enumerate(tests):
            if not isinstance(item, dict):
                raise ValueError(f"Item {i} is not an object: {item}")

            if "prompt" not in item:
                raise ValueError(f"Item {i} missing 'prompt' field: {item}")

            prompt = item["prompt"]
            if not isinstance(prompt, dict):
                raise ValueError(f"Item {i} 'prompt' is not an object: {prompt}")

            if "content" not in prompt:
                raise ValueError(f"Item {i} missing 'prompt.content' field: {prompt}")

            if not isinstance(prompt["content"], str):
                raise ValueError(f"Item {i} 'prompt.content' is not a string: {prompt['content']}")

            # Add the paraphrase with required structure
            paraphrases.append({"prompt": {"content": prompt["content"], "language_code": "en"}})

        return paraphrases

    def _generate_paraphrases(self, test: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate paraphrased versions of a single test.

        Args:
            test: The original test to paraphrase

        Returns:
            List[Dict[str, Any]]: List of paraphrased versions, exactly num_paraphrases in length
        """
        # Extract the prompt content, handling different possible test structures
        original_prompt = ""
        if isinstance(test.get("prompt"), dict):
            original_prompt = test["prompt"].get("content", "")
        elif isinstance(test.get("prompt"), str):
            original_prompt = test["prompt"]
        else:
            original_prompt = str(test.get("prompt", ""))

        # Format the system prompt
        formatted_prompt = self.system_prompt.render(
            original_prompt=original_prompt,
            num_paraphrases=self.num_paraphrases,
        )

        # Use utility function for LLM calls
        content = retry_llm_call(self.model, formatted_prompt)

        # Parse and validate the response
        paraphrases = self._parse_paraphrases(content)

        # Ensure we get exactly num_paraphrases results
        if len(paraphrases) < self.num_paraphrases:
            for attempt in range(2):
                additional_content = retry_llm_call(self.model, formatted_prompt)
                additional_paraphrases = self._parse_paraphrases(additional_content)
                paraphrases.extend(additional_paraphrases)

                if len(paraphrases) >= self.num_paraphrases:
                    break

            if len(paraphrases) < self.num_paraphrases:
                raise ValueError(
                    f"LLM returned {len(paraphrases)} paraphrases, expected {self.num_paraphrases}"
                )

        # Take exactly num_paraphrases results
        paraphrases = paraphrases[: self.num_paraphrases]

        # Create paraphrased test objects with all the necessary metadata
        return [
            {
                "prompt": {
                    "content": p["prompt"]["content"],
                    "language_code": "en",
                },
                "behavior": test.get("behavior", ""),
                "category": test.get("category", ""),
                "topic": test.get("topic", ""),
                "metadata": {
                    "generated_by": "ParaphrasingSynthesizer",
                    "original_test_id": test.get("id", "unknown"),
                    "is_paraphrase": True,
                    "original_content": original_prompt,
                },
            }
            for p in paraphrases
        ]

    def generate(self, **kwargs: Any) -> TestSet:
        """
        Generate paraphrased versions of all tests in the test set.

        Args:
            **kwargs: Supports:
                num_paraphrases (int): Number of paraphrases to generate per test. Defaults to 2.

        Returns:
            TestSet: A TestSet containing original tests plus their paraphrased versions,
                    with paraphrases appearing immediately after their original test
        """
        self.num_paraphrases = kwargs.get("num_paraphrases", 2)
        original_tests = self.test_set.to_dict()
        all_tests = []

        def process_test(test: Dict[str, Any]) -> None:
            """Process a single test and its paraphrases."""
            all_tests.append(test)  # Add original
            paraphrases = self._generate_paraphrases(test)  # Generate paraphrases
            all_tests.extend(paraphrases)  # Add paraphrases

        # Use the base class's progress bar
        self._process_with_progress(
            original_tests,
            process_test,
            desc=f"Generating {self.num_paraphrases} paraphrases per test",
        )

        # Use utility function to create TestSet
        return create_test_set(
            all_tests,
            model=self.model,
            synthesizer_name="ParaphrasingSynthesizer",
            batch_size=self.batch_size,
            original_test_set_id=self.test_set.fields.get("id", "unknown"),
            num_paraphrases=self.num_paraphrases,
            num_original_tests=len(original_tests),
            total_tests=len(all_tests),
        )
