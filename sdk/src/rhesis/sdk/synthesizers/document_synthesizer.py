from pprint import pprint
from typing import List, Optional, Union

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.services.chunker import (
    ChunkingStrategy,
    IdentityChunker,
    SemanticChunker,
)
from rhesis.sdk.services.extractor import (
    SourceBase,
    SourceType,
)
from rhesis.sdk.synthesizers.context_synthesizer import ContextSynthesizer


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


if __name__ == "__main__":
    sources = [
        SourceBase(
            name="test",
            description="test",
            type=SourceType.WEBSITE,
            metadata={
                "url": "https://sebastianraschka.com/blog/2025/llm-evaluation-4-approaches.html"
            },
        ),
    ]
    a = KnowledgeSynthesizer(
        prompt="generate test cases for the following document",
        sources=sources,
        model="gemini",
        chunking_strategy=IdentityChunker(),
    )
    tests = a.generate(num_tests=5)
    pprint(tests.tests)
    print("finished")
