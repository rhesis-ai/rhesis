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
        max_chunk_length: int = 1000,  # characters
    ):
        """
        Initialize the context generator.

        Args:
            default_chunks: Default number of chunks to select (defaults to 5)
            random_selection: If True, randomly select chunks; if False, take first N
            separator: String to use between chunks when assembling context
            max_chunk_length: Maximum characters per chunk
        """
        self.default_chunks = default_chunks
        self.random_selection = random_selection
        self.separator = separator
        self.max_chunk_length = max_chunk_length

    def create_chunks_from_text(
        self, text: str, max_chunk_length: Optional[int] = None
    ) -> List[str]:
        """
        Create chunks from text based on length constraints.

        Args:
            text: Text to chunk
            max_chunk_length: Override default chunk length

        Returns:
            List of text chunks
        """
        if not text:
            return []

        chunk_length = max_chunk_length or self.max_chunk_length
        chunks = []
        start = 0

        while start < len(text):
            # Calculate end position for this chunk
            end = start + chunk_length

            # If this is not the last chunk, try to find a good break point
            if end < len(text):
                # Look for a good break point (newline, period, space)
                for i in range(end, max(start, end - 200), -1):
                    if text[i] in ["\n", ".", " "]:
                        end = i + 1
                        break

            # Extract the chunk
            chunk = text[start:end].strip()
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)

            # Move to next chunk
            start = end
            if start >= len(text):
                break

        return chunks

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
