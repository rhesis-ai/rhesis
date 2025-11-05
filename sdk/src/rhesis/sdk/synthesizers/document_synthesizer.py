from pprint import pprint
from typing import List, Optional, Union

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.services.chunker import (
    ChunkingStrategy,
    IdentityChunker,
    SemanticChunker,
    SourceChunker,
)
from rhesis.sdk.services.extractor import (
    ExtractedSource,
    SourceBase,
    SourceExtractor,
    SourceType,
)
from rhesis.sdk.synthesizers.context_synthesizer import ContextSynthesizer
from rhesis.sdk.synthesizers.utils import create_test_set


class KnowledgeSynthesizer:
    """Simple synthesizer that generates test cases from documents"""

    def __init__(
        self,
        prompt: str,
        sources: List[SourceBase],
        batch_size: int = 20,
        chunking_strategy: ChunkingStrategy = SemanticChunker(max_tokens_per_chunk=1000),
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        """
        Initialize the document synthesizer.

        Args:
            batch_size: Maximum number of tests to generate in a single LLM call
            max_tokens_per_chunk: Maximum tokens per chunk used by the chunk generator
        """
        if isinstance(model, str):
            self.model = get_model(model)
        else:
            self.model = model

        self.sources = sources
        self.prompt = prompt
        self.batch_size = batch_size
        self.chunker = chunking_strategy

        self.context_synthesizer = ContextSynthesizer(
            prompt=self.prompt, batch_size=self.batch_size, model=self.model
        )

    def _process_sources(self, sources: List[SourceBase]) -> List[ExtractedSource]:
        """
        Process sources and extract text with source tracking.

        Args:
            sources: List of SourceBase objects

        Returns:
            List of ExtractedSource objects
        """
        return SourceExtractor()(sources)

    def _compute_tests_per_chunk(self, num_tests: int, num_chunks: int) -> list[int]:
        tests_per_chunk = [(num_tests + i) // num_chunks for i in range(num_chunks)]
        tests_per_chunk.reverse()
        return tests_per_chunk

    def generate(
        self,
        num_tests: int = 5,
    ) -> "TestSet":
        """
        Generate synthetic data using the complete pipeline.

        Args:
            documents: List of Document objects with 'name', 'description',
                and either 'path' (file path) or 'content' (raw text)
            num_tests: Total number of tests to generate (hard budget)

        Returns:
            TestSet: Generated tests with per-test chunk metadata and overall coverage info
        """

        # Process documents with source tracking
        processed_sources = self._process_sources(self.sources)

        chunks = SourceChunker(processed_sources, strategy=self.chunker).chunk()

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

            result = self.context_synthesizer.generate(
                num_tests=tests_per_chunk[i],
                context=chunk.content,
            )

            # Add context and document mapping to each test
            for test in result.tests:
                test["metadata"] = {
                    **(test.get("metadata") or {}),
                    "sources": chunk.source.model_dump(),
                    "generated_by": "DocumentSynthesizer",
                    "context_index": i,
                    "context_length": len(chunk.content),
                }

            all_test_cases.extend(result.tests)

        # Get document names for TestSet metadata
        source_names = [chunk.source.name for chunk in chunks]

        # Use the same approach as PromptSynthesizer
        return create_test_set(
            all_test_cases,
            model=self.model,
            synthesizer_name="DocumentSynthesizer",
            batch_size=self.batch_size,
            generation_prompt=self.prompt,
            num_tests=len(all_test_cases),
            requested_tests=num_tests,
            documents_used=source_names,
            coverage_percent=coverage_percent,
            contexts_total=len(chunks),
            contexts_used=used_chunks,
            tests_per_context=tests_per_chunk,
        )


if __name__ == "__main__":
    sources = [
        # SourceBase(
        #     name="test",
        #     description="test",
        #     type=SourceType.DOCUMENT,
        #     metadata={"path": "/Users/arek/Desktop/rhesis/README.md"},
        # ),
        SourceBase(
            name="test",
            description="test",
            type=SourceType.WEBSITE,
            metadata={
                "url": "https://sebastianraschka.com/blog/2025/llm-evaluation-4-approaches.html"
            },
        ),
    ]

    synthesizer = KnowledgeSynthesizer(
        prompt="generate test cases for the following document",
        sources=sources,
        model="gemini",
        chunking_strategy=IdentityChunker(),
    )

    tests = synthesizer.generate(num_tests=5)
    pprint(tests.tests)
    print("finished")
