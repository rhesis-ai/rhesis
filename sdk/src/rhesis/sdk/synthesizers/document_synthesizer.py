import random
from typing import List, Literal, Optional, TypedDict, Union

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.services.context_generator import ContextGenerator
from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.synthesizers.prompt_synthesizer import PromptSynthesizer
from rhesis.sdk.synthesizers.utils import create_test_set
from rhesis.sdk.utils import count_tokens


class Document(TypedDict):
    """Document structure for the DocumentSynthesizer."""

    name: str
    description: str
    path: Optional[str]  # File path (used if 'content' is not provided)
    content: Optional[str]  # Raw text content (overrides 'path' if provided)


class DocumentSynthesizer(TestSetSynthesizer):
    """Simple synthesizer that generates test cases from documents"""

    def __init__(
        self,
        prompt: str,
        batch_size: int = 20,
        system_prompt: Optional[str] = None,
        max_context_tokens: int = 1000,
        strategy: Literal["sequential", "random"] = "random",
        model: Optional[Union[str, BaseLLM]] = None,
    ):
        """
        Initialize the document synthesizer.

        Args:
            prompt: The generation prompt to use for test case generation
            batch_size: Maximum number of tests to generate in a single LLM call
            system_prompt: Optional custom system prompt template to override the default
            max_context_tokens: Maximum tokens per context used by the ContextGenerator
            strategy: Context selection strategy - "sequential" (from start) or "random" (shuffled)
        """
        if isinstance(model, str) or model is None:
            self.model = get_model(model)
        else:
            self.model = model

        self.prompt_synthesizer = PromptSynthesizer(
            prompt=prompt, batch_size=batch_size, model=model
        )
        super().__init__(batch_size=self.prompt_synthesizer.batch_size)

        self.context_generator = ContextGenerator(max_context_tokens=max_context_tokens)
        self.max_context_tokens = max_context_tokens
        self.strategy = strategy
        self.document_extractor = DocumentExtractor()

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
        self, content: str, contexts: List[str], tests_per_contexts: List[int]
    ) -> tuple[float, int]:
        """Compute coverage percent and number of used contexts based on token counts."""
        total_tokens = count_tokens(content)
        if total_tokens is None:
            raise ValueError("Failed to count tokens - content may be malformed or invalid")

        used_context_tokens = 0
        used_contexts = 0
        for i, context in enumerate(contexts):
            if i < len(tests_per_contexts) and tests_per_contexts[i] > 0:
                used_context_tokens += count_tokens(context)
                used_contexts += 1

        coverage_percent = (
            round((used_context_tokens / total_tokens) * 100, 2) if total_tokens else 0.0
        )
        return coverage_percent, used_contexts

    def _print_generation_info(
        self,
        documents: List[Document],
        content: str,
        contexts: List[str],
        tests_per_contexts: List[int],
        num_tests: int,
        tests_per_context: Optional[int],
    ) -> None:
        """Print informative summary about document processing and test generation plan."""
        total_tokens = count_tokens(content)
        if total_tokens is None:
            raise ValueError("Failed to count tokens - content may be malformed or invalid")

        actual_tests = sum(tests_per_contexts)
        num_contexts = len(contexts)

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

    def extract_text_from_documents(self, documents: List[Document]) -> str:
        """
        Extract text from documents using the existing DocumentExtractor.

        Args:
            documents: List of document dictionaries with the following keys:
                - 'name': Name of the document.
                - 'description': Required description.
                - 'path': File path to the document (used if 'content' is not provided).
                - 'content': Raw text content of the document. Overrides 'path' if both are given.

        Returns:
            Combined text from all documents, joined by a double newline ("\n\n").
        """
        try:
            extracted_texts = self.document_extractor.extract(documents)
            # Join all extracted texts with a double newline
            return "\n\n".join(extracted_texts.values())
        except Exception as e:
            print(f"Warning: Failed to extract some documents: {e}")
            return ""

    def generate(
        self,
        documents: List[Document],
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

        # Extract content from documents
        content = self.extract_text_from_documents(documents)

        # Get document names for mapping
        document_names = [doc["name"] for doc in documents]

        # Use the existing context_generator (returns all contexts based on token limits)
        contexts = self.context_generator.generate_contexts(content)

        if not contexts:
            raise ValueError("No contexts could be generated from the documents")

        # Apply strategy: shuffle contexts if random strategy is selected
        if self.strategy == "random":
            random.shuffle(contexts)

        all_test_cases = []

        # Compute distribution of tests across contexts
        num_contexts = len(contexts)
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
            content=content,
            contexts=contexts,
            tests_per_contexts=tests_per_contexts,
            num_tests=num_tests,
            tests_per_context=tests_per_context,
        )

        # Generate tests for each context
        for i, context in enumerate(contexts):
            per_context = tests_per_contexts[i]
            if per_context <= 0:
                continue
            print(
                f"Generating tests for context {i + 1}/{len(contexts)} ({len(context)} characters)"
            )

            result = self.prompt_synthesizer.generate(num_tests=per_context, context=context)

            # Add context and document mapping to each test
            for test in result.tests:
                test["metadata"] = {
                    **(test.get("metadata") or {}),
                    "generated_by": "DocumentSynthesizer",
                    "context_index": i,
                    "context_length": len(context),
                    "context": context,
                    "documents_used": document_names,
                }

            all_test_cases.extend(result.tests)

        # Compute coverage of document based on tokens for used contexts
        coverage_percent, used_contexts = self._compute_coverage(
            content, contexts, tests_per_contexts
        )

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
            contexts_total=len(contexts),
            contexts_used=used_contexts,
            tests_per_context=tests_per_context,
        )
