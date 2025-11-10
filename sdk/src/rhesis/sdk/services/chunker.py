"""Context generator service for creating context from various sources."""

import re
from abc import ABC, abstractmethod
from typing import List

from pydantic import BaseModel

from rhesis.sdk.services.extractor import ExtractedSource, SourceBase
from rhesis.sdk.utils import count_tokens


class Chunk(BaseModel):
    """A chunk of text with a source metadata and a content"""

    source: SourceBase
    content: str


class ChunkingStrategy(ABC):
    """Abstract base class for chunkers."""

    @abstractmethod
    def chunk(self, text: str) -> List[str]:
        """Chunk the text into a list of chunks."""
        pass


class ChunkingService:
    """Chunk sources using a selected chunking strategy."""

    def __init__(self, sources: list[ExtractedSource], strategy: ChunkingStrategy):
        self.sources = sources
        self.strategy = strategy

    def chunk(self) -> List[Chunk]:
        chunks = []
        for source in self.sources:
            text_chunks = self.strategy.chunk(source.content)

            source_metadata = SourceBase(**source.model_dump())

            for chunk in text_chunks:
                chunks.append(Chunk(source=source_metadata, content=chunk))
        return chunks


class IdentityChunker(ChunkingStrategy):
    """No chunking strategy."""

    def chunk(self, text: str) -> List[str]:
        """No chunking."""
        return [text]


class SemanticChunker(ChunkingStrategy):
    """Service for generating chunks of text from various sources using intelligent semantic
    chunking."""

    def __init__(
        self,
        max_tokens_per_chunk: int = 1500,
    ):
        """
        Initialize the context generator.

        Args:
            max_context_tokens: Maximum tokens per context (user preference)
        """
        self.max_context_tokens = min(max_tokens_per_chunk, 3000)

        if max_tokens_per_chunk > 3000:
            print(f"⚠️  Context size capped at 3000 tokens (you requested {max_tokens_per_chunk})")

    def chunk(self, text: str) -> List[str]:
        """
        Generate contexts using intelligent semantic chunking with hard size limits.

        Strategy:
        1. Identify semantic boundaries (headers, sections, paragraphs)
        2. Create contexts that respect these boundaries
        3. Enforce hard token limit; if a semantic span exceeds the context limit, split it abruptly
        4. If there are no internal boundaries, slice the text into token-capped windows
        """
        if not text:
            raise ValueError("Cannot generate contexts from empty text")

        text = text.strip()
        semantic_boundaries = self._identify_semantic_boundaries(text)

        # If no internal boundaries (just [0, len(text)]), slice linearly
        if len(semantic_boundaries) <= 2:
            contexts: List[str] = []
            start_pos = 0
            while start_pos < len(text):
                end_pos = self._find_token_capped_end(text, start_pos, len(text))
                chunk = text[start_pos:end_pos].strip()
                if chunk:
                    contexts.append(chunk)
                if end_pos <= start_pos:
                    break
                start_pos = end_pos
            return contexts

        # Create contexts from semantic boundaries with abrupt splits when needed
        contexts = self._create_contexts_from_boundaries(text, semantic_boundaries)

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

    def _create_contexts_from_boundaries(self, text: str, boundaries: List[int]) -> List[str]:
        """Create contexts from semantic boundaries."""
        contexts: List[str] = []

        # Start from the first boundary and create contexts sequentially
        start_idx = 0
        while start_idx < len(boundaries) - 1:
            # Find the best end boundary for this context
            end_idx = self._find_best_end_boundary(boundaries, start_idx, text)

            if end_idx <= start_idx:
                break

            # Extract context text
            start_pos = boundaries[start_idx]
            end_pos = boundaries[end_idx]
            context_text = text[start_pos:end_pos].strip()

            if context_text:
                # If the single span between adjacent boundaries exceeds token limit,
                # split it abruptly into token-capped windows
                span_tokens = count_tokens(text[start_pos:end_pos])
                if span_tokens is None:
                    raise ValueError("Failed to count tokens - text may be malformed or invalid")
                if end_idx == start_idx + 1 and span_tokens > self.max_context_tokens:
                    local_start = start_pos
                    while local_start < end_pos:
                        local_end = self._find_token_capped_end(text, local_start, end_pos)
                        piece = text[local_start:local_end].strip()
                        if piece:
                            contexts.append(piece)
                        if local_end <= local_start:
                            break
                        local_start = local_end
                else:
                    contexts.append(context_text)

            # Move to the next boundary
            start_idx = end_idx

        return contexts

    def _find_best_end_boundary(self, boundaries: List[int], start_idx: int, text: str) -> int:
        """Find the best end boundary for a context."""
        start_pos = boundaries[start_idx]

        # Find the furthest boundary within size limit
        for i in range(start_idx + 1, len(boundaries)):
            end_pos = boundaries[i]
            token_len = count_tokens(text[start_pos:end_pos])
            if token_len is None:
                raise ValueError("Failed to count tokens - text may be malformed or invalid")

            if token_len > self.max_context_tokens:
                # We've exceeded the limit, go back one
                if i > start_idx + 1:
                    return i - 1
                else:
                    # Even the smallest context is too big, use it anyway
                    return i

        # Use the last boundary
        return len(boundaries) - 1

    def _find_token_capped_end(self, text: str, start_pos: int, hard_end: int) -> int:
        """Find the furthest end index within hard_end that stays under the token limit."""
        low = start_pos + 1
        high = hard_end
        best = None
        while low <= high:
            mid = (low + high) // 2
            tokens = count_tokens(text[start_pos:mid])
            if tokens is None:
                raise ValueError("Failed to count tokens - text may be malformed or invalid")
            if tokens <= self.max_context_tokens:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        if best is None:
            return min(start_pos + 1, hard_end)
        return best
