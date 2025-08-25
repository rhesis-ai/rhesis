from typing import Any, Dict, List, Optional

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.services import LLMService
from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
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
        documents: Optional[List[Dict]] = None,
    ):
        """
        Initialize the PromptSynthesizer.
        Args:
            prompt: The generation prompt to use
            batch_size: Maximum number of tests to generate in a single LLM call (reduced default
            for stability)
            system_prompt: Optional custom system prompt template to override the default
            documents: Optional list of documents to extract content from. Each document should
            have:
                - name (str): Unique identifier or label for the document
                - description (str): Short description of the document's purpose or content
                - path (str): Local file path (optional, can be empty if content is provided)
                - content (str): Pre-provided document content (optional)
        """

        super().__init__(batch_size=batch_size)
        self.prompt = prompt
        self.documents = documents or []

        # Initialize document extractor for processing document files
        self.document_extractor = DocumentExtractor()

        # Extract content from documents if provided
        self.extracted_documents = {}
        if self.documents:
            try:
                self.extracted_documents = self.document_extractor.extract(self.documents)
            except Exception as e:
                print(f"Warning: Failed to extract some documents: {e}")

        # Set system prompt using utility function
        self.system_prompt = load_prompt_template(self.__class__.__name__, system_prompt)

        self.llm_service = LLMService()

    def _generate_batch(self, num_tests: int) -> List[Dict[str, Any]]:
        """Generate a batch of test cases with improved error handling."""
        # Prepare context for the prompt
        context = ""
        if self.extracted_documents:
            context = "\n\n".join(
                [
                    f"Document '{name}':\n{content}"
                    for name, content in self.extracted_documents.items()
                ]
            )

        formatted_prompt = self.system_prompt.render(
            generation_prompt=self.prompt, num_tests=num_tests, context=context
        )

        # Use utility function for retry logic
        response = retry_llm_call(self.llm_service, formatted_prompt)

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
                        "documents_used": list(self.extracted_documents.keys())
                        if self.extracted_documents
                        else [],
                    },
                }
                for test in valid_test_cases[:num_tests]
            ]

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
            all_test_cases = self._generate_batch(num_tests)

        # Ensure we have some test cases
        if not all_test_cases:
            raise ValueError("Failed to generate any valid test cases")

        # Use utility function to create TestSet
        return create_test_set(
            all_test_cases,
            synthesizer_name="PromptSynthesizer",
            batch_size=self.batch_size,
            generation_prompt=self.prompt,
            num_tests=len(all_test_cases),
            requested_tests=num_tests,
            documents_used=list(self.extracted_documents.keys())
            if self.extracted_documents
            else [],
        )
