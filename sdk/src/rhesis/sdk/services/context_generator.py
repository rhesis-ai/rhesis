"""Context generator service for creating context from various sources."""

import re
from typing import List


class ContextGenerator:
    """Service for generating context from various sources using intelligent semantic chunking."""

    def __init__(
        self,
        max_context_tokens: int = 1000,  # User's preferred max
        absolute_max_context_tokens: int = 2000,  # Hard safety limit
    ):
        """
        Initialize the context generator.

        Args:
            max_context_tokens: Maximum tokens per context (user preference)
            absolute_max_context_tokens: Hard limit that cannot be exceeded
        """
        self.max_context_tokens = max_context_tokens
        self.absolute_max_context_tokens = absolute_max_context_tokens

        # Validate user input
        if self.max_context_tokens > self.absolute_max_context_tokens:
            raise ValueError(
                f"max_context_tokens ({max_context_tokens}) cannot exceed "
                f"absolute_max_context_tokens ({absolute_max_context_tokens})"
            )

    def generate_contexts(self, text: str, num_tests: int) -> List[str]:
        """
        Generate contexts directly from text using intelligent semantic chunking.

        Args:
            text: Input text to process
            num_tests: Number of contexts to generate

        Returns:
            List of context strings, each sized appropriately for prompts
        """
        if not text:
            return []

        return self.create_contexts_from_text(text, num_tests)

    def create_contexts_from_text(self, text: str, num_tests: int) -> List[str]:
        """
        Create contexts using intelligent semantic chunking.

        Strategy:
        1. Identify semantic boundaries (headers, sections, paragraphs)
        2. Create contexts that respect these boundaries
        """
        # First, identify semantic boundaries
        semantic_boundaries = self._identify_semantic_boundaries(text)

        if not semantic_boundaries:
            # Fallback to simple chunking
            return self._simple_chunking(text, num_tests)

        # Create contexts from semantic boundaries
        contexts = self._create_contexts_from_boundaries(text, semantic_boundaries, num_tests)

        return contexts

    def _identify_semantic_boundaries(self, text: str) -> List[int]:
        """Identify semantic boundaries in the text."""
        boundaries = [0]  # Start of text

        lines = text.split("\n")
        current_pos = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline

            # Check for markdown headers
            if re.match(r"^#{1,6}\s+", line):
                boundaries.append(current_pos)

            # Check for section separators
            elif re.match(r"^[-*_]{3,}$", line):
                boundaries.append(current_pos)

            # Check for major paragraph breaks (double newlines)
            elif line.strip() == "" and current_pos > 0:
                # Look ahead to see if this is a paragraph break
                next_non_empty = current_pos + line_length
                while (
                    next_non_empty < len(text)
                    and text[next_non_empty : next_non_empty + 1].isspace()
                ):
                    next_non_empty += 1

                if next_non_empty < len(text) and text[next_non_empty : next_non_empty + 1] not in [
                    "#",
                    "-",
                    "*",
                    "_",
                ]:
                    boundaries.append(current_pos)

            current_pos += line_length

        # Add end of text
        boundaries.append(len(text))

        return boundaries

    def _create_contexts_from_boundaries(
        self, text: str, boundaries: List[int], num_tests: int
    ) -> List[str]:
        """Create contexts from semantic boundaries."""
        contexts = []
        max_context_chars = self.max_context_tokens * 4

        # Start from the first boundary and create contexts sequentially
        start_idx = 0
        while start_idx < len(boundaries) - 1 and len(contexts) < num_tests:
            # Find the best end boundary for this context
            end_idx = self._find_best_end_boundary(boundaries, start_idx, max_context_chars, text)

            if end_idx <= start_idx:
                break

            # Extract context text
            start_pos = boundaries[start_idx]
            end_pos = boundaries[end_idx]
            context_text = text[start_pos:end_pos].strip()

            if context_text and len(context_text) >= max_context_chars * 0.5:  # Threshould
                contexts.append(context_text)

            # Move to the next boundary
            start_idx = end_idx

        return contexts

    def _find_best_end_boundary(
        self, boundaries: List[int], start_idx: int, max_chars: int, text: str
    ) -> int:
        """Find the best end boundary for a context."""
        start_pos = boundaries[start_idx]

        # Find the furthest boundary within size limit
        for i in range(start_idx + 1, len(boundaries)):
            end_pos = boundaries[i]
            context_length = end_pos - start_pos

            if context_length > max_chars:
                # We've exceeded the limit, go back one
                if i > start_idx + 1:
                    return i - 1
                else:
                    # Even the smallest context is too big, use it anyway
                    return i

        # Use the last boundary
        return len(boundaries) - 1

    def _simple_chunking(self, text: str, num_tests: int) -> List[str]:
        """Fallback simple chunking when semantic boundaries aren't found."""
        contexts = []
        max_context_chars = self.max_context_tokens * 4

        start = 0
        while start < len(text) and len(contexts) < num_tests:
            end = self._find_context_boundary(text, start, max_context_chars)
            context_text = text[start:end].strip()

            if context_text:
                contexts.append(context_text)

            start = end

        return contexts

    def _find_context_boundary(self, text: str, start: int, max_chars: int) -> int:
        """Find the best boundary for a context piece."""
        end = min(start + max_chars, len(text))

        # If we're at the end, return it
        if end == len(text):
            return end

        # Look for good break points, prioritizing markdown structure
        for i in range(end, max(start, end - 300), -1):
            # Prefer markdown headers
            if text[i] == "#" and (i == 0 or text[i - 1] == "\n"):
                return i

            # Then prefer double newlines (paragraph breaks)
            if text[i : i + 2] == "\n\n":
                return i + 2

            # Then prefer single newlines
            if text[i] == "\n":
                return i + 1

            # Then prefer periods
            if text[i] == ".":
                return i + 1

        # If no good break point, return the calculated end
        return end
