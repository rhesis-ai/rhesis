import random
from typing import List, Literal, Optional, Union

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
from rhesis.sdk.utils import count_tokens


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
        strategy: Literal["sequential", "random"] = "random",
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        """
        Initialize the document synthesizer.

        Args:
            batch_size: Maximum number of tests to generate in a single LLM call
            max_context_tokens: Maximum tokens per context used by the ContextGenerator
            strategy: Context selection strategy - "sequential" (from start) or "random" (shuffled)
        """
        if isinstance(model, str):
            self.model = get_model(model)
        else:
            self.model = model

        self.sources = sources
        self.prompt = prompt
        self.batch_size = batch_size
        self.context_generator = ContextGenerator(max_context_tokens=max_context_tokens)
        self.max_context_tokens = max_context_tokens
        self.strategy = strategy

        self.context_synthesizer = ContextSynthesizer(
            prompt=self.prompt, batch_size=self.batch_size, model=self.model
        )

    def _compute_tests_distribution(
        self,
        num_contexts: int,
        num_tests: int,
        tests_per_context: Optional[int] = 2,
    ) -> List[int]:
        """Compute how many tests to generate per context without exceeding num_tests."""
        if num_contexts == 0:
            raise ValueError("No contexts available for test generation.")
        if tests_per_context is not None:
            max_total = tests_per_context * num_contexts
            budget = min(num_tests, max_total)
            effective = min(tests_per_context, budget // num_contexts)
            tests_per_contexts = [effective] * num_contexts
            used = effective * num_contexts
            remainder = max(0, budget - used)
            for i in range(min(remainder, num_contexts)):
                tests_per_contexts[i] += 1
            return tests_per_contexts

        base = num_tests // num_contexts
        remainder = num_tests % num_contexts
        return [base + (1 if i < remainder else 0) for i in range(num_contexts)]

    def _compute_coverage(
        self,
        processed_sources: List[ExtractedSource],
        contexts_with_sources: List[ContextWithSource],
        tests_per_contexts: List[int],
    ) -> tuple[float, int]:
        """Compute coverage percent and number of used contexts based on token counts."""
        total_tokens = sum([count_tokens(source.content) for source in processed_sources])

        used_context_tokens = 0
        used_contexts = 0
        for i, context in enumerate(contexts_with_sources):
            if i < len(tests_per_contexts) and tests_per_contexts[i] > 0:
                context_tokens = count_tokens(context.content)
                if context_tokens:
                    used_context_tokens += context_tokens
                used_contexts += 1

        coverage_percent = (
            round((used_context_tokens / total_tokens) * 100, 2) if total_tokens else 0.0
        )
        return coverage_percent, used_contexts

    def _print_generation_info(
        self,
        processed_sources: List[ExtractedSource],
        contexts_with_sources: List[ContextWithSource],
        tests_per_contexts: List[int],
        num_tests: int,
        tests_per_context: Optional[int],
    ) -> None:
        """Print informative summary about document processing and test generation plan."""
        total_tokens = sum([count_tokens(source.content) for source in processed_sources])

        actual_tests = sum(tests_per_contexts)
        num_contexts = len(contexts_with_sources)

        print("\n📄 Document Analysis:")
        print(f"   • {len(processed_sources)} source(s) processed")
        print(f"   • {total_tokens:,} total tokens extracted")
        print(f"   • {num_contexts} context(s) created (max {self.max_context_tokens} tokens each)")
        print(f"   • Strategy: {self.strategy} context selection")

        print("\n🧪 Test Generation Plan:")
        if tests_per_context is not None:
            ideal_total = tests_per_context * num_contexts

            requested_msg = (
                f"   • Requested: {tests_per_context} tests/context × "
                f"{num_contexts} contexts = {ideal_total} tests"
            )

            if ideal_total > num_tests:
                print(requested_msg)
                print(f"   • ⚠️  Capped at num_tests limit: {actual_tests} tests will be generated")
                print(
                    "   • Effective tests per context: "
                    f"~{actual_tests // num_contexts} (remainder distributed to first contexts)"
                )
            elif ideal_total < num_tests:
                print(requested_msg)
                print(
                    f"   • ✅ Within num_tests limit ({num_tests}): generating {actual_tests} tests"
                )
            else:
                print(
                    f"   • Generating {tests_per_context} tests/context × "
                    f"{num_contexts} contexts = {actual_tests} tests"
                )
        else:
            print(f"   • Distributing {num_tests} tests evenly across {num_contexts} contexts")
            print(
                f"   • ~{num_tests // num_contexts} tests per context "
                "(remainder distributed to first contexts)"
            )

        print(f"   • Total tests to generate: {actual_tests}")

        # Warn if many contexts won't be used due to low num_tests
        unused_contexts = sum(1 for count in tests_per_contexts if count == 0)
        if unused_contexts > 0:
            coverage_percent = ((num_contexts - unused_contexts) / num_contexts) * 100
            print("\n⚠️  Coverage Warning:")
            print(
                f"   • Only {num_contexts - unused_contexts}/{num_contexts} contexts will be used "
                f"({coverage_percent:.0f}% document coverage)"
            )
            print(f"   • {unused_contexts} context(s) skipped due to limited num_tests")
            print(
                "   • Consider: increase num_tests (>"
                f"{actual_tests}) or increase max_context_tokens (>"
                f"{self.max_context_tokens}) for fewer, larger contexts"
            )

        print()

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

        # Apply strategy: shuffle contexts if random strategy is selected
        if self.strategy == "random":
            random.shuffle(contexts_with_sources)

        all_test_cases = []

        # Compute distribution of tests across contexts
        num_contexts = len(contexts_with_sources)

        tests_per_contexts = self._compute_tests_distribution(
            num_contexts=num_contexts,
            num_tests=num_tests,
            tests_per_context=tests_per_context,
        )

        # Inform user about test distribution
        self._print_generation_info(
            processed_sources=processed_sources,
            contexts_with_sources=contexts_with_sources,
            tests_per_contexts=tests_per_contexts,
            num_tests=num_tests,
            tests_per_context=tests_per_context,
        )

        # Generate tests for each context
        for i, context in enumerate(contexts_with_sources):
            num_tests_per_context = tests_per_contexts[i]
            if num_tests_per_context <= 0:
                continue
            print(
                f"Generating tests for context {i + 1}/{len(contexts_with_sources)} "
                f"({len(context.content)} characters)"
            )

            result = self.context_synthesizer.generate(
                num_tests=num_tests_per_context,
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

    tests = synthesizer.generate(num_tests=4, tests_per_context=2)

    print(tests.tests)
    print("finished")
