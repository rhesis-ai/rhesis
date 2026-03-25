"""Context generator service for creating context from various sources."""

import warnings
from abc import ABC, abstractmethod
from typing import List, Union

import tiktoken
from chonkie import (
    RecursiveChunker as ChonkieRecursiveChunker,
)
from chonkie import (
    SentenceChunker as ChonkieSentenceChunker,
)
from chonkie import (
    TokenChunker as ChonkieTokenChunker,
)
from pydantic import BaseModel

from rhesis.sdk.services.extractor import ExtractedSource, SourceSpecification

DEFAULT_ENCODING = "cl100k_base"


class Chunk(BaseModel):
    """A chunk of text with source metadata and content."""

    source: SourceSpecification
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
            source_metadata = SourceSpecification(**source.model_dump())
            for chunk in text_chunks:
                chunks.append(Chunk(source=source_metadata, content=chunk))
        return chunks


class IdentityChunker(ChunkingStrategy):
    """No chunking strategy."""

    def chunk(self, text: str) -> List[str]:
        """No chunking."""
        """No chunking."""
        return [text]


class TokenChunker(ChunkingStrategy):
    """Splits text into fixed-size token chunks

    Args:
        chunk_size: Maximum number of tokens per chunk.
        chunk_overlap: Overlapping tokens between chunks. Can be a float (e.g. 0.1 = 10% overlap).
        encoding_name: Tiktoken encoding name. Defaults to cl100k_base.
    """

    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: Union[int, float] = 0,
        encoding_name: str = DEFAULT_ENCODING,
    ):
        self._chunker = ChonkieTokenChunker(
            tokenizer=tiktoken.get_encoding(encoding_name),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk(self, text: str) -> List[str]:
        return [c.text for c in self._chunker.chunk(text)]


class SentenceChunker(ChunkingStrategy):
    """Splits text at sentence boundaries while respecting a token size limit.

    Keeps sentences intact and never cuts mid-sentence.

    Args:
        chunk_size: Maximum number of tokens per chunk.
        chunk_overlap: Overlapping tokens between chunks.
        min_sentences_per_chunk: Minimum number of sentences per chunk.
        encoding_name: Tiktoken encoding name. Defaults to cl100k_base.
    """

    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 0,
        min_sentences_per_chunk: int = 1,
        encoding_name: str = DEFAULT_ENCODING,
    ):
        self._chunker = ChonkieSentenceChunker(
            tokenizer=tiktoken.get_encoding(encoding_name),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_sentences_per_chunk=min_sentences_per_chunk,
        )

    def chunk(self, text: str) -> List[str]:
        return [c.text for c in self._chunker.chunk(text)]


class RecursiveChunker(ChunkingStrategy):
    """Recursively splits text using a hierarchy of delimiters.

    Tries to split on large structural boundaries first (paragraphs, headers),
    then falls back to finer ones (sentences, words) until chunks fit within
    the token limit. Best for long, well-structured documents like papers or
    markdown files.

    Args:
        chunk_size: Maximum number of tokens per chunk.
        encoding_name: Tiktoken encoding name. Defaults to cl100k_base.
    """

    def __init__(
        self,
        chunk_size: int = 1500,
        encoding_name: str = DEFAULT_ENCODING,
    ):
        self._chunker = ChonkieRecursiveChunker(
            tokenizer=tiktoken.get_encoding(encoding_name),
            chunk_size=chunk_size,
        )

    @classmethod
    def from_recipe(cls, recipe: str = "markdown", lang: str = "en") -> "RecursiveChunker":
        """Create a RecursiveChunker pre-configured for a known format.

        Args:
            recipe: Recipe name (e.g. "markdown"). See available recipes at
                https://huggingface.co/datasets/chonkie-ai/recipes
            lang: Language code (e.g. "en", "hi").
        """
        instance = cls.__new__(cls)
        instance._chunker = ChonkieRecursiveChunker.from_recipe(recipe, lang=lang)
        return instance

    def chunk(self, text: str) -> List[str]:
        return [c.text for c in self._chunker.chunk(text)]


class SemanticChunker(RecursiveChunker):
    """Deprecated. Use RecursiveChunker instead.

    The old SemanticChunker split on structural boundaries (headers, paragraphs)
    with a token cap: this is exactly what RecursiveChunker does. This class
    is kept as an alias for backwards compatibility.
    """

    def __init__(
        self,
        chunk_size: int = 1500,
        max_tokens_per_chunk: int = None,
        encoding_name: str = DEFAULT_ENCODING,
    ):
        warnings.warn(
            "SemanticChunker is deprecated and will be removed in a future version. "
            "Use RecursiveChunker instead. "
            "The 'max_tokens_per_chunk' argument is also deprecated; use 'chunk_size' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if max_tokens_per_chunk is not None:
            chunk_size = max_tokens_per_chunk
        super().__init__(chunk_size=chunk_size, encoding_name=encoding_name)
