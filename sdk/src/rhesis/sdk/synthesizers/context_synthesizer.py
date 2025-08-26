"""Simple context synthesizer for selecting document chunks and generating synthetic data."""

import random
from typing import Any, List, Optional

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.synthesizers.prompt_synthesizer import PromptSynthesizer


class ContextSynthesizer(TestSetSynthesizer):
    """Synthesizer that selects chunks and generates test sets using PromptSynthesizer."""

    def __init__(
        self,
        prompt_synthesizer: PromptSynthesizer,
        default_chunks: int = 5,
        random_selection: bool = False,
    ):
        """
        Initialize the context synthesizer.

        Args:
            prompt_synthesizer: PromptSynthesizer instance to use for generating synthetic data
            default_chunks: Default number of chunks to select (defaults to 5)
            random_selection: If True, randomly select chunks; if False, take first N
        """
        super().__init__()
        self.prompt_synthesizer = prompt_synthesizer
        self.default_chunks = default_chunks
        self.random_selection = random_selection

    def select_chunks(self, chunks: List[str], num_chunks: Optional[int] = None) -> List[str]:
        """
        Select chunks for context.

        Args:
            chunks: List of text chunks
            num_chunks: Number of chunks to select (uses default_chunks if not specified)

        Returns:
            List of selected chunk texts
        """
        if not chunks:
            return []

        # Determine how many chunks to select
        target_count = num_chunks or self.default_chunks
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

    def generate(self, **kwargs: Any) -> TestSet:
        """
        Generate synthetic data using selected chunks as context.

        Args:
            **kwargs: Keyword arguments including:
                - chunks: List of text chunks to select from
                - num_chunks: Number of chunks to select
                - Any other arguments to pass to PromptSynthesizer.generate()

        Returns:
            TestSet: Generated synthetic data using the context
        """
        chunks = kwargs.get("chunks", [])
        num_chunks = kwargs.get("num_chunks", None)

        # Select chunks for context
        selected_chunks = self.select_chunks(chunks, num_chunks)
        context = self.assemble_context(selected_chunks)

        # Update the prompt synthesizer's context
        self.prompt_synthesizer.context = context

        # Generate using the updated prompt synthesizer
        result = self.prompt_synthesizer.generate(**kwargs)

        # Add context metadata with namespacing
        result.metadata = result.metadata or {}
        result.metadata["context_synthesizer"] = {
            "chunks_selected": len(selected_chunks),
            "total_chunks_available": len(chunks),
            "context_length": len(context),
            "selection_strategy": "random" if self.random_selection else "sequential",
            "chunk_metadata": kwargs.get("chunk_metadata", {}),
        }

        return result
