from typing import List, Optional, Union

from pydantic import BaseModel

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.services.context_generator import ContextGenerator
from rhesis.sdk.services.extractor import (
    DocumentExtractor,
    ExtractedSource,
    NotionExtractor,
    SourceBase,
    SourceType,
    WebsiteExtractor,
)
from rhesis.sdk.synthesizers.context_synthesizer import ContextSynthesizer
from rhesis.sdk.synthesizers.utils import create_test_set


class ContextWithSource(BaseModel):
    source: SourceBase
    content: str


# context is a list of chunks of text
# and every chunk has a source, and a content


class KnowledgeSynthesizer:
    """Simple synthesizer that generates test cases from documents"""

    def __init__(
        self,
        prompt: str,
        sources: List[SourceBase],
        batch_size: int = 20,
        max_context_tokens: int = 1000,
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        """
        Initialize the document synthesizer.

        Args:
            batch_size: Maximum number of tests to generate in a single LLM call
            max_context_tokens: Maximum tokens per context used by the ContextGenerator
        """
        if isinstance(model, str):
            self.model = get_model(model)
        else:
            self.model = model

        self.sources = sources
        self.prompt = prompt
        self.batch_size = batch_size
        self.context_generator = ContextGenerator(max_context_tokens=max_context_tokens)

        self.context_synthesizer = ContextSynthesizer(
            prompt=self.prompt, batch_size=self.batch_size, model=self.model
        )

    def process_sources(self, sources: List[SourceBase]) -> List[ExtractedSource]:
        """
        Process sources and extract text with source tracking.

        Args:
            sources: List of SourceBase objects

        Returns:
            List of ExtractedSource objects
        """
        try:
            extracted_sources = []
            for source in sources:
                if source.type == SourceType.DOCUMENT:
                    extracted_source = DocumentExtractor().extract(source)
                elif source.type == SourceType.WEBSITE:
                    extracted_source = WebsiteExtractor().extract(source)
                elif source.type == SourceType.NOTION:
                    extracted_source = NotionExtractor().extract(source)
                else:
                    raise ValueError(f"Unsupported source type: {source.type}")
                extracted_sources.append(extracted_source)
            return extracted_sources

        except Exception as e:
            print(f"Warning: Failed to extract some documents: {e}")
            return []

    def generate(
        self,
        num_tests: int = 5,
        tests_per_context: Optional[int] = None,
    ) -> "TestSet":
        """
        Generate synthetic data using the complete pipeline.

        Args:
            documents: List of Document objects with 'name', 'description',
                and either 'path' (file path) or 'content' (raw text)
            num_tests: Total number of tests to generate (hard budget)
            tests_per_context: Target tests per context.
                Generates tests_per_context * num_contexts total, never exceeding num_tests.

        Returns:
            TestSet: Generated tests with per-test context metadata and overall coverage info
        """

        # Process documents with source tracking
        processed_sources = self.process_sources(self.sources)

        # Generate contexts with source tracking
        contexts_with_sources = []
        for source in processed_sources:
            source.content = source.content.strip()
            source_contexts = self.context_generator.generate_contexts(source.content)
            source = SourceBase(**source.model_dump())
            for context in source_contexts:
                contexts_with_sources.append(ContextWithSource(source=source, content=context))

        if num_tests < len(contexts_with_sources):
            raise ValueError(
                "num_tests must be greater than or equal to the number of chunks. Current number "
                f"of chunks: {len(contexts_with_sources)}"
            )

        tests_per_chunk = num_tests // len(contexts_with_sources)
        print(
            f"Generate {tests_per_chunk} tests per chunk. \n "
            f"In total, {len(contexts_with_sources) * tests_per_chunk} tests will be generated."
        )

        all_test_cases = []

        # Generate tests for each context
        for i, context in enumerate(contexts_with_sources):
            print(
                f"Generating tests for context {i + 1}/{len(contexts_with_sources)} "
                f"({len(context.content)} characters)"
            )

            result = self.context_synthesizer.generate(
                num_tests=tests_per_chunk,
                context=context.content,
            )

            # Add context and document mapping to each test
            for test in result.tests:
                test["metadata"] = {
                    **(test.get("metadata") or {}),
                    "sources": context.source.model_dump(),
                    "generated_by": "DocumentSynthesizer",
                    "context_index": i,
                    "context_length": len(context.content),
                }

            all_test_cases.extend(result.tests)

        # Compute coverage of document based on tokens for used contexts
        coverage_percent, used_contexts = self._compute_coverage(
            processed_sources, contexts_with_sources, tests_per_contexts
        )

        # Get document names for TestSet metadata
        source_names = [context.source.name for context in contexts_with_sources]

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
            contexts_total=len(contexts_with_sources),
            contexts_used=used_contexts,
            tests_per_context=tests_per_context,
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
        prompt="generate test cases for the following document", sources=sources, model="gemini"
    )

    tests = synthesizer.generate(num_tests=4)

    print(tests.tests)
    print("finished")
