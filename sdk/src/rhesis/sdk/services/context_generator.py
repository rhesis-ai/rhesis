"""Context generator service for creating context from various sources."""

import random
from typing import Any, Dict, List, Optional


class ContextGenerator:
    """Service for generating context from various sources like documents, chunks, etc."""

    def __init__(
        self,
        default_chunks: int = 5,
        random_selection: bool = False,
        separator: str = "\n\n",
    ):
        """
        Initialize the context generator.

        Args:
            default_chunks: Default number of chunks to select (defaults to 5)
            random_selection: If True, randomly select chunks; if False, take first N
            separator: String to use between chunks when assembling context
        """
        self.default_chunks = default_chunks
        self.random_selection = random_selection
        self.separator = separator

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

    def assemble_context(self, chunks: List[str], separator: Optional[str] = None) -> str:
        """
        Combine chunks into a single context string.

        Args:
            chunks: List of chunk texts
            separator: String to use between chunks (uses instance default if not specified)

        Returns:
            Combined context string
        """
        if not chunks:
            return ""

        sep = separator or self.separator
        return sep.join(chunks)

    def generate_context_from_chunks(
        self, chunks: List[str], num_chunks: Optional[int] = None, separator: Optional[str] = None
    ) -> str:
        """
        Generate context from chunks by selecting and assembling them.

        Args:
            chunks: List of text chunks
            num_chunks: Number of chunks to select
            separator: String to use between chunks

        Returns:
            Combined context string
        """
        selected_chunks = self.select_chunks(chunks, num_chunks)
        return self.assemble_context(selected_chunks, separator)

    def get_context_metadata(
        self,
        chunks: List[str],
        selected_chunks: List[str],
        chunk_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate metadata about the context generation process.

        Args:
            chunks: Original list of chunks
            selected_chunks: Chunks that were selected for context
            chunk_metadata: Additional metadata about chunks

        Returns:
            Dictionary containing context generation metadata
        """
        return {
            "chunks_selected": len(selected_chunks),
            "total_chunks_available": len(chunks),
            "context_length": len(self.assemble_context(selected_chunks)),
            "selection_strategy": "random" if self.random_selection else "sequential",
            "chunk_metadata": chunk_metadata or {},
        }
