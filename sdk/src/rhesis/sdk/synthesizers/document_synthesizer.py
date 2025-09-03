"""Simple document synthesizer for extracting text and creating chunks."""

from typing import Any, List, Optional

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.services.context_generator import ContextGenerator
from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.synthesizers.prompt_synthesizer import PromptSynthesizer
from rhesis.sdk.synthesizers.utils import create_test_set
from rhesis.sdk.utils import count_tokens


class DocumentSynthesizer(TestSetSynthesizer):
    """Simple synthesizer that extracts text from documents"""

    def __init__(
        self,
        prompt: str,
        batch_size: int = None,
        system_prompt: Optional[str] = None,
        max_context_tokens: int = 1000,
        context_generator: Optional[ContextGenerator] = None,
    ):
        """
        Initialize the document synthesizer.

        Args:
            prompt: The generation prompt to use for test case generation
            batch_size: Maximum number of tests to generate in a single LLM call
            system_prompt: Optional custom system prompt template to override the default
            max_context_tokens: Maximum tokens per context used by the ContextGenerator
            context_generator: ContextGenerator instance for creating context (uses default if None)
        """
        # Create PromptSynthesizer with the provided arguments (let it use its own defaults)
        prompt_kwargs = {"prompt": prompt, "context": ""}
        if batch_size is not None:
            prompt_kwargs["batch_size"] = batch_size
        if system_prompt is not None:
            prompt_kwargs["system_prompt"] = system_prompt

        self.prompt_synthesizer = PromptSynthesizer(**prompt_kwargs)
        super().__init__(batch_size=self.prompt_synthesizer.batch_size)

        self.context_generator = ContextGenerator(max_context_tokens=max_context_tokens)
        self.max_context_tokens = max_context_tokens
        self.document_extractor = DocumentExtractor()

    def _compute_tests_distribution(
        self,
        num_contexts: int,
        num_tests: int,
        tests_per_context: Optional[int],
    ) -> List[int]:
        """Compute how many tests to generate per context without exceeding num_tests."""
        if num_contexts <= 0:
            return []

        if tests_per_context is not None:
            max_total = tests_per_context * num_contexts
            budget = min(num_tests, max_total)
            effective = min(tests_per_context, budget // num_contexts)
            counts = [effective] * num_contexts
            used = effective * num_contexts
            remainder = max(0, budget - used)
            for i in range(min(remainder, num_contexts)):
                counts[i] += 1
            return counts

        base = num_tests // num_contexts
        remainder = num_tests % num_contexts
        return [base + (1 if i < remainder else 0) for i in range(num_contexts)]

    def _compute_coverage(
        self, content: str, contexts: List[str], counts: List[int]
    ) -> tuple[float, int]:
        """Compute coverage percent and number of used contexts based on token counts."""
        total_tokens = count_tokens(content) or 0
        if total_tokens <= 0:
            return 0.0, 0

        used_context_tokens = 0
        used_contexts = 0
        for i, ctx in enumerate(contexts):
            if i < len(counts) and counts[i] > 0:
                used_context_tokens += count_tokens(ctx) or 0
                used_contexts += 1

        coverage_percent = (
            round((used_context_tokens / total_tokens) * 100, 2) if total_tokens else 0.0
        )
        return coverage_percent, used_contexts

    def _print_generation_info(
        self,
        documents: List[dict],
        content: str,
        contexts: List[str],
        counts: List[int],
        num_tests: int,
        tests_per_context_param: Optional[int],
    ) -> None:
        """Print informative summary about document processing and test generation plan."""
        total_tokens = count_tokens(content) or 0
        actual_tests = sum(counts)
        n = len(contexts)

        print("\n📄 Document Analysis:")
        print(f"   • {len(documents)} document(s) processed")
        print(f"   • {total_tokens:,} total tokens extracted")
        print(f"   • {n} context(s) created (max {self.max_context_tokens} tokens each)")

        print("\n🧪 Test Generation Plan:")
        if tests_per_context_param is not None:
            ideal_total = tests_per_context_param * n

            requested_msg = (
                f"   • Requested: {tests_per_context_param} tests/context × "
                f"{n} contexts = {ideal_total} tests"
            )

            if ideal_total > num_tests:
                print(requested_msg)
                print(f"   • ⚠️  Capped at num_tests limit: {actual_tests} tests will be generated")
                print(
                    "   • Effective tests per context: "
                    f"~{actual_tests // n} (remainder distributed to first contexts)"
                )
            elif ideal_total < num_tests:
                print(requested_msg)
                print(
                    f"   • ✅ Within num_tests limit ({num_tests}): generating {actual_tests} tests"
                )
            else:
                print(
                    f"   • Generating {tests_per_context_param} tests/context × "
                    f"{n} contexts = {actual_tests} tests"
                )
        else:
            print(f"   • Distributing {num_tests} tests evenly across {n} contexts")
            print(
                f"   • ~{num_tests // n} tests per context "
                "(remainder distributed to first contexts)"
            )

        print(f"   • Total tests to generate: {actual_tests}")

        # Warn if many contexts won't be used due to low num_tests
        unused_contexts = sum(1 for count in counts if count == 0)
        if unused_contexts > 0:
            coverage_percent = ((n - unused_contexts) / n) * 100
            print("\n⚠️  Coverage Warning:")
            print(
                f"   • Only {n - unused_contexts}/{n} contexts will be used "
                f"({coverage_percent:.0f}% document coverage)"
            )
            print(f"   • {unused_contexts} context(s) skipped due to limited num_tests")
            print(
                "   • Consider: increase num_tests (>"
                f"{actual_tests}) or increase max_context_tokens (>"
                f"{self.max_context_tokens}) for fewer, larger contexts"
            )

        print()

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
            Combined text from all documents, joined by a double newline ("\n\n").
        """
        try:
            extracted_texts = self.document_extractor.extract(documents)
            # Join all extracted texts with a double newline
            return "\n\n".join(extracted_texts.values())
        except Exception as e:
            print(f"Warning: Failed to extract some documents: {e}")
            return ""

    def generate(self, **kwargs: Any) -> "TestSet":
        """
        Generate synthetic data using the complete pipeline.

        Args:
            **kwargs: Keyword arguments including:
                - documents: List of document dictionaries
                - num_tests: Total number of tests to generate (hard budget)
                - tests_per_context (optional): Target tests per context.
                    Generates tests_per_context * num_contexts total, never exceeding num_tests.
                - Any other arguments to pass to PromptSynthesizer.generate()

        Returns:
            TestSet: Generated tests with per-test context metadata and overall coverage info
        """
        documents = kwargs.get("documents", [])
        num_tests = kwargs.get("num_tests", 5)  # Total desired tests
        tests_per_context_param = kwargs.get("tests_per_context", None)

        # Extract content from documents
        content = self.extract_text_from_documents(documents)

        # Get document names for mapping
        document_names = [doc["name"] for doc in documents]

        # Use the existing context_generator (returns all contexts based on token limits)
        contexts = self.context_generator.generate_contexts(content)

        if not contexts:
            raise ValueError("No contexts could be generated from the documents")

        all_test_cases = []

        # Compute distribution of tests across contexts
        n = len(contexts)
        if n <= 0:
            raise ValueError("No contexts available for test generation")

        counts = self._compute_tests_distribution(
            num_contexts=n, num_tests=num_tests, tests_per_context=tests_per_context_param
        )

        # Inform user about test distribution
        self._print_generation_info(
            documents=documents,
            content=content,
            contexts=contexts,
            counts=counts,
            num_tests=num_tests,
            tests_per_context_param=tests_per_context_param,
        )

        # Generate tests for each context
        for i, context in enumerate(contexts):
            per_ctx = counts[i]
            if per_ctx <= 0:
                continue
            print(
                f"Generating tests for context {i + 1}/{len(contexts)} ({len(context)} characters)"
            )

            # Update the prompt synthesizer's context
            self.prompt_synthesizer.context = context

            # Generate tests for this context; override num_tests while keeping other kwargs
            # Filter out DocumentSynthesizer-specific kwargs before passing to PromptSynthesizer
            prompt_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k not in ("documents", "tests_per_context", "max_context_tokens")
            }
            result = self.prompt_synthesizer.generate(**{**prompt_kwargs, "num_tests": per_ctx})

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

        # Compute coverage of document based on tokens for used contexts
        coverage_percent, used_contexts = self._compute_coverage(content, contexts, counts)

        # Use the same approach as PromptSynthesizer
        return create_test_set(
            all_test_cases,
            synthesizer_name="DocumentSynthesizer",
            batch_size=self.batch_size,
            generation_prompt=self.prompt_synthesizer.prompt,
            num_tests=len(all_test_cases),
            requested_tests=num_tests,
            documents_used=document_names,
            coverage_percent=coverage_percent,
            contexts_total=len(contexts),
            contexts_used=used_contexts,
            tests_per_context=tests_per_context_param,
        )
