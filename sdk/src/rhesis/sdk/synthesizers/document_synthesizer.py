"""Simple document synthesizer for extracting text and creating chunks."""

from typing import Any, List, Optional

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.services.context_generator import ContextGenerator
from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.synthesizers.prompt_synthesizer import PromptSynthesizer
from rhesis.sdk.synthesizers.utils import create_test_set


class DocumentSynthesizer(TestSetSynthesizer):
    """Simple synthesizer that extracts text from documents"""

    def __init__(
        self,
        prompt_synthesizer: PromptSynthesizer,
        context_generator: Optional[ContextGenerator] = None,
        max_context_tokens: int = 1000,  # Use tokens instead of characters
        separator: str = "\n\n",
    ):
        """
        Initialize the document synthesizer.

        Args:
            prompt_synthesizer: PromptSynthesizer instance to use for generating synthetic data
            context_generator: ContextGenerator instance for creating context (uses default if None)
            max_context_tokens: Maximum tokens per context
            separator: String to use when joining chunks (legacy, not used in new approach)
        """
        super().__init__()
        self.prompt_synthesizer = prompt_synthesizer
        self.context_generator = ContextGenerator(max_context_tokens=max_context_tokens)
        self.max_context_tokens = max_context_tokens
        self.separator = separator
        self.document_extractor = DocumentExtractor()

    def extract_text_from_documents(self, documents: List[dict]) -> str:
        """
        Extract text from documents using the existing DocumentExtractor.

        Args:
            documents: List of document dictionaries with the following keys:
                - 'name': Name of the document.
                - 'description': Required description.
                - 'path': File path to the document (used if 'content' is not provided).
                - 'content': Raw text content of the document. Overrides 'path' if both are given.

        Returns:
            Combined text from all documents
        """
        try:
            extracted_texts = self.document_extractor.extract(documents)
            # Join all extracted texts with separator
            return self.separator.join(extracted_texts.values())
        except Exception as e:
            print(f"Warning: Failed to extract some documents: {e}")
            return ""

    def generate(self, **kwargs: Any) -> "TestSet":
        """
        Generate synthetic data using the complete pipeline.

        Args:
            **kwargs: Keyword arguments including:
                - documents: List of document dictionaries
                - num_tests: Number of tests to generate
                - Any other arguments to pass to PromptSynthesizer.generate()

        Returns:
            TestSet: Generated synthetic data from the complete pipeline
        """
        documents = kwargs.get("documents", [])
        num_tests = kwargs.get("num_tests", 5)  # Default to 5 tests

        # Extract content from documents
        content = self.extract_text_from_documents(documents)

        # Get document names for mapping
        document_names = [doc["name"] for doc in documents]

        # Use the existing context_generator
        contexts = self.context_generator.generate_contexts(content, num_tests)

        if not contexts:
            raise ValueError("No contexts could be generated from the documents")

        all_test_cases = []

        # Generate tests for each context
        for i, context in enumerate(contexts):
            print(
                f"Generating tests for context {i + 1}/{len(contexts)} ({len(context)} characters)"
            )

            # Update the prompt synthesizer's context
            self.prompt_synthesizer.context = context

            # Calculate tests per context
            tests_per_context = max(1, num_tests // len(contexts))

            # Generate tests for this context; override num_tests while keeping other kwargs
            result = self.prompt_synthesizer.generate(**{**kwargs, "num_tests": tests_per_context})

            # Add context and document mapping to each test
            for test in result.tests:
                test["metadata"] = {
                    **(test.get("metadata") or {}),
                    "context_index": i,
                    "context_length": len(context),
                    "context": context,
                    "documents_used": document_names,
                }

            all_test_cases.extend(result.tests)

        # Use the same approach as PromptSynthesizer
        return create_test_set(
            all_test_cases,
            synthesizer_name="DocumentSynthesizer",
            batch_size=self.batch_size,
            generation_prompt=self.prompt_synthesizer.prompt,
            num_tests=len(all_test_cases),
            requested_tests=num_tests,
            documents_used=document_names,
        )
