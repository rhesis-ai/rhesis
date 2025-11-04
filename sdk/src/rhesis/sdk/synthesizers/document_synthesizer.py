import random
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.context_generator import ContextGenerator
from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.synthesizers.config_synthesizer import GenerationConfig
from rhesis.sdk.synthesizers.context_synthesizer import ContextSynthesizer
from rhesis.sdk.synthesizers.utils import create_test_set
from rhesis.sdk.types import Document
from rhesis.sdk.utils import count_tokens


class DocumentSynthesizer:
    """Simple synthesizer that generates test cases from documents"""

    def __init__(
        self,
        prompt: str,
        documents: List[Document],
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
        self.context_synthesizer = ContextSynthesizer(
            prompt=prompt, context=None, batch_size=batch_size, model=model
        )

        self.documents = documents

        self.document_extractor = DocumentExtractor()
        self.context_generator = ContextGenerator(max_context_tokens=max_context_tokens)
        self.max_context_tokens = max_context_tokens
        self.strategy = strategy

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
        processed_documents: List[Dict[str, str]],
        contexts_with_sources: List[Dict[str, str]],
        tests_per_contexts: List[int],
    ) -> tuple[float, int]:
        """Compute coverage percent and number of used contexts based on token counts."""
        total_tokens = sum(count_tokens(doc["content"]) for doc in processed_documents)
        if total_tokens is None or total_tokens == 0:
            raise ValueError("Failed to count tokens - content may be malformed or invalid")

        used_context_tokens = 0
        used_contexts = 0
        for i, context_doc in enumerate(contexts_with_sources):
            if i < len(tests_per_contexts) and tests_per_contexts[i] > 0:
                context_tokens = count_tokens(context_doc["content"])
                if context_tokens:
                    used_context_tokens += context_tokens
                used_contexts += 1

        coverage_percent = (
            round((used_context_tokens / total_tokens) * 100, 2) if total_tokens else 0.0
        )
        return coverage_percent, used_contexts

    def _print_generation_info(
        self,
        documents: List[Document],
        processed_documents: List[Dict[str, str]],
        contexts_with_sources: List[Dict[str, str]],
        tests_per_contexts: List[int],
        num_tests: int,
        tests_per_context: Optional[int],
    ) -> None:
        """Print informative summary about document processing and test generation plan."""
        total_tokens = sum(count_tokens(doc["content"]) for doc in processed_documents)
        if total_tokens is None or total_tokens == 0:
            raise ValueError("Failed to count tokens - content may be malformed or invalid")

        actual_tests = sum(tests_per_contexts)
        num_contexts = len(contexts_with_sources)

        print("\n📄 Document Analysis:")
        print(f"   • {len(documents)} document(s) processed")
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

    def process_documents(self, documents: List[Document]) -> List[Dict[str, str]]:
        """
        Process documents and extract text with source tracking.

        Args:
            documents: List of Document dataclass objects

        Returns:
            List of dictionaries with the following keys:
                - 'source': Source identifier (filename from path or name)
                - 'name': Name of the document.
                - 'description': Description of the document.
                - 'content': Raw text content of the document.
        """
        try:
            extracted_texts = self.document_extractor.extract(documents)
            return [
                {
                    "source": Path(doc.path).name if doc.path else doc.name,
                    "name": doc.name,
                    "description": doc.description,
                    "content": content,
                }
                for doc in documents
                for content in [extracted_texts.get(doc.name)]
                if content
            ]
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
        processed_documents = self.process_documents(self.documents)

        if not processed_documents:
            raise ValueError("No content could be extracted from documents")

        # Generate contexts with source tracking
        contexts_with_sources = []
        for doc in processed_documents:
            if doc["content"].strip():
                doc_contexts = self.context_generator.generate_contexts(doc["content"])
                for context in doc_contexts:
                    contexts_with_sources.append(
                        {
                            "source": doc["source"],
                            "name": doc["name"],
                            "description": doc["description"],
                            "content": context,
                        }
                    )

        if not contexts_with_sources:
            raise ValueError("No contexts could be generated from the documents")

        # Apply strategy: shuffle contexts if random strategy is selected
        if self.strategy == "random":
            random.shuffle(contexts_with_sources)

        all_test_cases = []

        # Compute distribution of tests across contexts
        num_contexts = len(contexts_with_sources)
        if num_contexts <= 0:
            raise ValueError("No contexts available for test generation")

        tests_per_contexts = self._compute_tests_distribution(
            num_contexts=num_contexts,
            num_tests=num_tests,
            tests_per_context=tests_per_context,
        )

        # Inform user about test distribution
        self._print_generation_info(
            documents=documents,
            processed_documents=processed_documents,
            contexts_with_sources=contexts_with_sources,
            tests_per_contexts=tests_per_contexts,
            num_tests=num_tests,
            tests_per_context=tests_per_context,
        )

        # Generate tests for each context
        for i, context_doc in enumerate(contexts_with_sources):
            per_context = tests_per_contexts[i]
            if per_context <= 0:
                continue
            print(
                f"Generating tests for context {i + 1}/{len(contexts_with_sources)} "
                f"({len(context_doc['content'])} characters)"
            )

            result = self.prompt_synthesizer.generate(
                num_tests=per_context,
                context=context_doc["content"],
                config=self.config,
                chip_states=self.chip_states,
                rated_samples=self.rated_samples,
                previous_messages=self.previous_messages,
            )

            # Add context and document mapping to each test
            for test in result.tests:
                test["metadata"] = {
                    **(test.get("metadata") or {}),
                    "sources": [
                        {
                            "source": context_doc["source"],
                            "name": context_doc["name"],
                            "description": context_doc["description"],
                            "content": context_doc["content"],
                        }
                    ],
                    "generated_by": "DocumentSynthesizer",
                    "context_index": i,
                    "context_length": len(context_doc["content"]),
                }

            all_test_cases.extend(result.tests)

        # Compute coverage of document based on tokens for used contexts
        coverage_percent, used_contexts = self._compute_coverage(
            processed_documents, contexts_with_sources, tests_per_contexts
        )

        # Get document names for TestSet metadata
        document_names = [doc["name"] for doc in processed_documents]

        # Use the same approach as PromptSynthesizer
        return create_test_set(
            all_test_cases,
            model=self.model,
            synthesizer_name="DocumentSynthesizer",
            batch_size=self.batch_size,
            generation_prompt=self.prompt_synthesizer.prompt,
            num_tests=len(all_test_cases),
            requested_tests=num_tests,
            documents_used=document_names,
            coverage_percent=coverage_percent,
            contexts_total=len(contexts_with_sources),
            contexts_used=used_contexts,
            tests_per_context=tests_per_context,
        )


if __name__ == "__main__":
    config = GenerationConfig(
        project_context="Web application that allows users to search for and book flights.",
        behaviors=["Robustness"],
        topics=["Flights", "Booking", "Search"],
        categories=["Security", "Performance"],
        specific_requirements="The LLM should be able to detect frauds",
        test_type="config",
        output_format="json",
    )
    synthesizer = DocumentSynthesizer(prompt=" ", config=config, model="gemini")
    document = Document(
        name="test",
        description="test",
        path="/Users/arek/Downloads/sample.pdf",
    )
    tests = synthesizer.generate(documents=[document], num_tests=3)
    print(tests.tests)
    print("finished")
