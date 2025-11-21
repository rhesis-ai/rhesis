from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, cast

from pydantic import BaseModel
from tqdm.auto import tqdm

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.enums import TestType
from rhesis.sdk.models import get_model
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.chunker import (
    ChunkingService,
    ChunkingStrategy,
    SemanticChunker,
)
from rhesis.sdk.services.extractor import (
    ExtractionService,
    SourceSpecification,
)
from rhesis.sdk.synthesizers.utils import (
    create_test_set,
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
    # Note: test_type is NOT included in the schema sent to the LLM
    # It will be added programmatically after generation


class Tests(BaseModel):
    tests: List[Test]


class TestSetSynthesizer(ABC):
    """Base class for all test set synthesizers."""

    prompt_template_file: str

    def __init__(
        self,
        batch_size: int = 5,
        model: Optional[Union[str, BaseLLM]] = None,
        sources: Optional[List[SourceSpecification]] = None,
        chunking_strategy: Optional[ChunkingStrategy] = SemanticChunker(max_tokens_per_chunk=1500),
    ):
        """
        Initialize the base synthesizer.

        Args:
            batch_size: Maximum number of items to process in a single LLM call
            model: The model to use for generation (string name or BaseLLM instance)
            sources: Optional list of source specifications to extract content from
            chunking_strategy: Strategy for chunking source content
        """
        self.batch_size = batch_size
        self.prompt_template = load_prompt_template(self.prompt_template_file)
        self.sources = sources
        self.chunker = chunking_strategy

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
            str: The synthesizer name (e.g., "PromptSynthesizer", "ConfigSynthesizer")
        """
        return self.__class__.__name__

    def _compute_tests_per_chunk(self, num_tests: int, num_chunks: int) -> list[int]:
        tests_per_chunk = [(num_tests + i) // num_chunks for i in range(num_chunks)]
        tests_per_chunk.reverse()
        return tests_per_chunk

    def _generate_with_sources(
        self, num_tests: int, **kwargs: Any
    ) -> tuple[List[Dict[str, Any]], dict[str, Any]]:
        # Process documents with source tracking
        if not isinstance(self.sources, list) or not all(
            isinstance(source, SourceSpecification) for source in self.sources
        ):
            raise ValueError("sources must be a list of SourceBase objects")

        if self.chunker is None or not isinstance(self.chunker, ChunkingStrategy):
            raise ValueError("chunker must be a ChunkingStrategy object")

        processed_sources = ExtractionService.extract(self.sources)

        chunks = ChunkingService(processed_sources, strategy=self.chunker).chunk()

        tests_per_chunk = self._compute_tests_per_chunk(num_tests, len(chunks))
        if num_tests < len(chunks):
            print(
                f"number of tests is less than number of chunks. Current number of chunks: "
                f"{len(chunks)} \n"
                f"Number of tests: {num_tests}"
            )
        else:
            print(f"Generate {num_tests} tests \n ")

        if num_tests >= len(chunks):
            coverage_percent = 100
            used_chunks = len(chunks)
        else:
            coverage_percent = num_tests / len(chunks)
            used_chunks = num_tests

        all_test_cases = []

        # Generate tests for each chunk
        for i, chunk in enumerate(chunks):
            if tests_per_chunk[i] == 0:
                continue
            print(
                f"Generating tests for chunk "
                f"{i + 1}/{min(num_tests, len(chunks))} "
                f"({tests_per_chunk[i]} tests)"
                f"({len(chunk.content)} characters)"
            )

            result = self._generate_without_sources(
                num_tests=tests_per_chunk[i],
                **kwargs,
                source=chunk.content,
            )

            # Add context and document mapping to each test
            for test in result:
                # Ensure test_type is set (should already be set by _generate_batch)
                if "test_type" not in test:
                    test["test_type"] = TestType.SINGLE_TURN.value

                test["metadata"] = {
                    **(test.get("metadata") or {}),
                    "sources": [
                        {
                            "source": chunk.source.name,
                            "name": chunk.source.name,
                            "description": chunk.source.description,
                            "content": chunk.content,
                        }
                    ],
                    "generated_by": self._get_synthesizer_name(),
                    "context_index": i,
                    "context_length": len(chunk.content),
                }

            all_test_cases.extend(result)

        # Get document names for TestSet metadata

        source_names = [chunk.source.name for chunk in chunks]
        test_set_metadata = {
            "documents_used": source_names,
            "coverage_percent": coverage_percent,
            "contexts_total": len(chunks),
            "contexts_used": used_chunks,
            "tests_per_context": tests_per_chunk,
        }
        return all_test_cases, test_set_metadata

    def _generate_without_sources(self, num_tests: int = 5, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Generate test cases with automatic chunking.

        Args:
            num_tests: Total number of test cases to generate. Defaults to 5.
            **kwargs: Additional keyword arguments for test set generation

        Returns:
            TestSet: A TestSet entity containing the generated test cases
        """

        if not isinstance(num_tests, int):
            raise TypeError("num_tests must be an integer")

        template_context = self._get_template_context(**kwargs)

        all_test_cases = []
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

        return all_test_cases

    def _generate_batch(
        self,
        num_tests: int,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Generate a batch of test cases with improved error handling."""
        template_context = {"num_tests": num_tests, **kwargs}
        prompt = self.prompt_template.render(**template_context)

        # Use utility function for retry logic
        # When schema is provided, generate() returns a Dict
        response = cast(Dict[str, Any], self.model.generate(prompt=prompt, schema=Tests))
        tests = response["tests"][:num_tests]

        tests = [
            {
                **test,
                "test_type": TestType.SINGLE_TURN.value,  # Set to Single-Turn
                "metadata": {
                    "generated_by": self._get_synthesizer_name(),
                },
            }
            for test in tests
        ]

        return tests

    def generate(self, num_tests: int = 5, **kwargs: Any) -> TestSet:
        """Generate test cases."""
        test_set_metadata = {}
        if self.sources is not None:
            tests, test_set_metadata = self._generate_with_sources(num_tests, **kwargs)
        else:
            tests = self._generate_without_sources(num_tests, **kwargs)

        # Use utility function to create TestSet
        return create_test_set(
            tests,
            model=self.model,
            synthesizer_name=self._get_synthesizer_name(),
            batch_size=self.batch_size,
            num_tests=len(tests),
            requested_tests=num_tests,
            **test_set_metadata,
        )
