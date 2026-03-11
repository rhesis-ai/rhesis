import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, cast

from pydantic import BaseModel

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

logger = logging.getLogger(__name__)


# Flat schema for LLM batch generation (easier for the model to produce).
# Repacked to nested Test structure after generation.
class FlatTest(BaseModel):
    prompt_content: str
    prompt_expected_response: str
    prompt_language_code: str
    behavior: str
    category: str
    topic: str


class FlatTests(BaseModel):
    tests: List[FlatTest]


_MIN_BATCH_SIZE = 1
_MAX_CONSECUTIVE_FAILURES = 3


class TestSetSynthesizer(ABC):
    """Base class for all test set synthesizers."""

    prompt_template_file: str

    def __init__(
        self,
        batch_size: int = 5,
        model: Optional[Union[str, BaseLLM]] = None,
        sources: Optional[List[SourceSpecification]] = None,
        chunking_strategy: Optional[ChunkingStrategy] = None,
    ):
        """
        Initialize the base synthesizer.

        Args:
            batch_size: Maximum number of items to process in a single LLM call
            model: The model to use for generation (string name or BaseLLM instance)
            sources: Optional list of source specifications to extract content from
            chunking_strategy: Strategy for chunking source content
                (defaults to SemanticChunker with 1500 max tokens per chunk)
        """
        if batch_size < _MIN_BATCH_SIZE:
            raise ValueError(f"batch_size must be >= {_MIN_BATCH_SIZE}, got {batch_size}")
        self.batch_size = batch_size
        self.prompt_template = load_prompt_template(self.prompt_template_file)
        self.sources = sources
        self.chunker = chunking_strategy or SemanticChunker(max_tokens_per_chunk=1500)

        if isinstance(model, str) or model is None:
            self.model = get_model(model)
        else:
            self.model = model

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

        logger.info(
            "[Synthesizer] _generate_with_sources: extracting %d sources",
            len(self.sources),
        )
        extract_start = time.time()
        processed_sources = ExtractionService.extract(self.sources)
        logger.info(
            "[Synthesizer] Extraction completed in %.1fs",
            time.time() - extract_start,
        )

        chunk_start = time.time()
        chunks = ChunkingService(processed_sources, strategy=self.chunker).chunk()
        logger.info(
            "[Synthesizer] Chunking completed in %.1fs: %d chunks from %d sources",
            time.time() - chunk_start,
            len(chunks),
            len(processed_sources),
        )

        tests_per_chunk = self._compute_tests_per_chunk(num_tests, len(chunks))
        if num_tests < len(chunks):
            logger.warning(
                "[Synthesizer] num_tests (%d) < num_chunks (%d), some chunks will be skipped",
                num_tests,
                len(chunks),
            )
        else:
            logger.info(
                "[Synthesizer] Generating %d tests across %d chunks",
                num_tests,
                len(chunks),
            )

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
            logger.info(
                "[Synthesizer] Chunk %d/%d: generating %d tests (%d chars content, source=%s)",
                i + 1,
                min(num_tests, len(chunks)),
                tests_per_chunk[i],
                len(chunk.content),
                chunk.source.name,
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

    def _process_batch_response(
        self,
        response: Any,
        expected_size: int,
        batch_index: int,
    ) -> List[Dict[str, Any]]:
        """Process a single response from model.generate or model.generate_batch."""
        if isinstance(response, dict) and "error" in response:
            logger.error(
                "[Synthesizer] Batch %d: LLM returned error: %s",
                batch_index,
                response["error"],
            )
            return []

        if not isinstance(response, dict) or "tests" not in response:
            logger.error(
                "[Synthesizer] Batch %d: unexpected response type=%s: %s",
                batch_index,
                type(response).__name__,
                str(response)[:500],
            )
            return []

        flat_tests = response["tests"][:expected_size]
        return [
            {
                **self._flat_test_to_nested(flat),
                "test_type": TestType.SINGLE_TURN.value,
                "metadata": {
                    "generated_by": self._get_synthesizer_name(),
                },
            }
            for flat in flat_tests
        ]

    def _generate_without_sources(self, num_tests: int = 5, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Generate test cases using model.generate_batch for parallel execution
        when num_tests > batch_size, with sequential retry on failures.

        Automatically reduces batch size on consecutive failures and retries.

        Args:
            num_tests: Total number of test cases to generate. Defaults to 5.
            **kwargs: Additional keyword arguments for test set generation

        Returns:
            List of test case dicts
        """
        if not isinstance(num_tests, int):
            raise TypeError("num_tests must be an integer")

        template_context = self._get_template_context(**kwargs)

        all_test_cases: List[Dict[str, Any]] = []
        generation_start = time.time()

        logger.info(
            "[Synthesizer] Starting generation: num_tests=%d, batch_size=%d, model=%s",
            num_tests,
            self.batch_size,
            getattr(self.model, "model_name", type(self.model).__name__),
        )

        try:
            batch_tests = self._generate_parallel_batches(num_tests, **template_context)
            all_test_cases.extend(batch_tests)
        except Exception:
            logger.exception(
                "[Synthesizer] Parallel batch generation failed, "
                "falling back to sequential generation"
            )

        remaining = num_tests - len(all_test_cases)
        if remaining > 0:
            sequential_tests = self._generate_with_retry(remaining, **template_context)
            all_test_cases.extend(sequential_tests)

        total_elapsed = time.time() - generation_start
        logger.info(
            "[Synthesizer] Generation complete: %d/%d tests in %.1fs (%.1f tests/sec)",
            len(all_test_cases),
            num_tests,
            total_elapsed,
            len(all_test_cases) / total_elapsed if total_elapsed > 0 else 0,
        )

        if not all_test_cases:
            raise ValueError("Failed to generate any valid test cases")

        return all_test_cases

    def _generate_with_retry(self, num_tests: int, **template_context: Any) -> List[Dict[str, Any]]:
        """Generate tests sequentially with batch size reduction on failure."""
        all_test_cases: List[Dict[str, Any]] = []
        remaining = num_tests
        current_batch_size = self.batch_size
        consecutive_failures = 0

        while remaining > 0:
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                logger.error(
                    "[Synthesizer] Stopping after %d consecutive failures "
                    "(batch_size=%d, generated=%d/%d)",
                    consecutive_failures,
                    current_batch_size,
                    len(all_test_cases),
                    num_tests,
                )
                break

            batch_request_size = min(remaining, current_batch_size)

            try:
                tests = self._generate_batch(batch_request_size, **template_context)
            except Exception:
                logger.exception(
                    "[Synthesizer] Exception in batch generation (batch_size=%d)",
                    batch_request_size,
                )
                tests = []

            if tests:
                all_test_cases.extend(tests)
                remaining -= len(tests)
                consecutive_failures = 0
                logger.info(
                    "[Synthesizer] Batch succeeded: %d tests (remaining=%d)",
                    len(tests),
                    remaining,
                )
            else:
                consecutive_failures += 1
                if current_batch_size > _MIN_BATCH_SIZE:
                    current_batch_size = max(_MIN_BATCH_SIZE, current_batch_size // 2)
                    logger.warning(
                        "[Synthesizer] Batch failed (attempt %d/%d), reducing batch size to %d",
                        consecutive_failures,
                        _MAX_CONSECUTIVE_FAILURES,
                        current_batch_size,
                    )
                else:
                    logger.warning(
                        "[Synthesizer] Batch failed (attempt %d/%d) at minimum batch size %d",
                        consecutive_failures,
                        _MAX_CONSECUTIVE_FAILURES,
                        _MIN_BATCH_SIZE,
                    )

        return all_test_cases

    def _generate_parallel_batches(
        self, num_tests: int, **template_context: Any
    ) -> List[Dict[str, Any]]:
        """Generate tests across multiple batches using model.generate_batch."""
        num_full_batches = num_tests // self.batch_size
        remainder = num_tests % self.batch_size

        batch_sizes = [self.batch_size] * num_full_batches
        if remainder > 0:
            batch_sizes.append(remainder)

        prompts = []
        for bs in batch_sizes:
            batch_context = {**template_context, "num_tests": bs}
            prompts.append(self.prompt_template.render(**batch_context))

        logger.info(
            "[Synthesizer] Parallel batch generation: %d batches (%d x %d + %d remainder)",
            len(batch_sizes),
            num_full_batches,
            self.batch_size,
            remainder,
        )

        batch_start = time.time()
        responses = cast(
            List[Dict[str, Any]],
            self.model.generate_batch(prompts=prompts, schema=FlatTests),
        )
        batch_elapsed = time.time() - batch_start

        if len(responses) != len(batch_sizes):
            raise ValueError(
                f"generate_batch returned {len(responses)} responses for "
                f"{len(batch_sizes)} prompts; counts must match"
            )

        all_tests: List[Dict[str, Any]] = []
        for i, (response, expected_size) in enumerate(zip(responses, batch_sizes)):
            tests = self._process_batch_response(response, expected_size, i + 1)
            all_tests.extend(tests)

        logger.info(
            "[Synthesizer] Parallel batch generation: %d tests across %d batches in %.1fs",
            len(all_tests),
            len(batch_sizes),
            batch_elapsed,
        )

        return all_tests

    def _flat_test_to_nested(self, flat: Dict[str, Any]) -> Dict[str, Any]:
        """Repack a flat test dict (LLM output) into the nested Test structure."""
        return {
            "prompt": {
                "content": flat["prompt_content"],
                "expected_response": flat["prompt_expected_response"],
                "language_code": flat["prompt_language_code"],
            },
            "behavior": flat["behavior"],
            "category": flat["category"],
            "topic": flat["topic"],
        }

    def _generate_batch(
        self,
        num_tests: int,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Generate a batch of test cases with improved error handling."""
        template_context = {**kwargs, "num_tests": num_tests}
        prompt = self.prompt_template.render(**template_context)

        logger.debug(
            "[Synthesizer] _generate_batch: calling model.generate for %d tests "
            "(prompt length=%d chars)",
            num_tests,
            len(prompt),
        )

        llm_start = time.time()
        response = cast(
            Dict[str, Any],
            self.model.generate(prompt=prompt, schema=FlatTests),
        )
        llm_elapsed = time.time() - llm_start

        logger.debug(
            "[Synthesizer] _generate_batch: LLM responded in %.1fs",
            llm_elapsed,
        )

        return self._process_batch_response(response, num_tests, batch_index=0)

    def generate(self, num_tests: int = 5, **kwargs: Any) -> TestSet:
        """Generate test cases."""
        logger.info(
            "[Synthesizer] generate() called: num_tests=%d, synthesizer=%s, "
            "has_sources=%s, model=%s",
            num_tests,
            self._get_synthesizer_name(),
            self.sources is not None,
            getattr(self.model, "model_name", type(self.model).__name__),
        )
        overall_start = time.time()

        test_set_metadata = {}
        if self.sources is not None:
            tests, test_set_metadata = self._generate_with_sources(num_tests, **kwargs)
        else:
            tests = self._generate_without_sources(num_tests, **kwargs)

        logger.info(
            "[Synthesizer] Test generation phase complete: %d tests in %.1fs, creating TestSet...",
            len(tests),
            time.time() - overall_start,
        )

        # Use utility function to create TestSet
        test_set = create_test_set(
            tests,
            model=self.model,
            synthesizer_name=self._get_synthesizer_name(),
            batch_size=self.batch_size,
            num_tests=len(tests),
            requested_tests=num_tests,
            **test_set_metadata,
        )

        total_elapsed = time.time() - overall_start
        logger.info(
            "[Synthesizer] generate() complete: %d tests, total time %.1fs",
            len(tests),
            total_elapsed,
        )
        return test_set
