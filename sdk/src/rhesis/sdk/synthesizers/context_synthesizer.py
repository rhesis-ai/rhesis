"""Simple context synthesizer for selecting document chunks."""

import random
from typing import Any, List, Optional

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.synthesizers.base import TestSetSynthesizer


class ContextSynthesizer(TestSetSynthesizer):
    """Simple synthesizer that selects chunks for context."""

    def __init__(
        self, batch_size: int = 5, max_chunks: Optional[int] = None, random_selection: bool = False
    ):
        """
        Initialize the context synthesizer.

        Args:
            batch_size: Maximum number of chunks to process in a single batch
            max_chunks: Maximum chunks to return (overrides batch_size if set)
            random_selection: If True, randomly select chunks; if False, take first N
        """
        super().__init__(batch_size=batch_size)
        self.max_chunks = max_chunks
        self.random_selection = random_selection

    def select_chunks(self, chunks: List[str], num_chunks: Optional[int] = None) -> List[str]:
        """
        Select chunks for context.

        Args:
            chunks: List of text chunks
            num_chunks: Number of chunks to select (uses batch_size if not specified)

        Returns:
            List of selected chunk texts
        """
        if not chunks:
            return []

        # Determine how many chunks to select
        target_count = num_chunks or self.max_chunks or self.batch_size
        target_count = min(target_count, len(chunks))

        if self.random_selection:
            return random.sample(chunks, target_count)
        else:
            return chunks[:target_count]

    def assemble_context(self, chunks: List[str], separator: str = "\n\n") -> str:
        """
        Combine chunks into a single context string.

        Args:
            chunks: List of chunk texts
            separator: String to use between chunks

        Returns:
            Combined context string
        """
        return separator.join(chunks)

    def generate(self, **kwargs: Any) -> "TestSet":
        """
        Generate context from chunks (required by base class).

        Args:
            **kwargs: Keyword arguments including:
                - chunks: List of text chunks
                - num_chunks: Number of chunks to select

        Returns:
            TestSet: A TestSet with the generated context
        """

        chunks = kwargs.get("chunks", [])
        num_chunks = kwargs.get("num_chunks", None)

        selected_chunks = self.select_chunks(chunks, num_chunks)
        context = self.assemble_context(selected_chunks)

        return TestSet(
            name="Generated Context",
            description=f"Context from {len(selected_chunks)} chunks",
            tests=[{"context": context, "chunks_used": len(selected_chunks)}],
            metadata={
                "synthesizer": "ContextSynthesizer",
                "chunks_selected": len(selected_chunks),
                "total_chunks_available": len(chunks),
            },
        )
