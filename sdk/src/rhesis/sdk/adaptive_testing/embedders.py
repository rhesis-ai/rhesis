from typing import List

import appdirs
import diskcache
import numpy as np
from sklearn.preprocessing import normalize

from rhesis.sdk.models import BaseEmbedder

_embedding_memory_cache = {}
_embedding_file_cache = diskcache.Cache(
    appdirs.user_cache_dir("adaptive_testing") + "/embeddings.diskcache"
)


class EmbedderAdapter:
    """Adapter that wraps a BaseEmbedder for use with adaptive testing caching.

    This adapter provides:
    - `name` property for cache key prefix
    - `__call__` method for batch embedding

    Args:
        embedder: A BaseEmbedder instance from rhesis.sdk.models
        replace_newlines: Whether to replace newlines with spaces (recommended for most models)
    """

    def __init__(self, embedder: BaseEmbedder, replace_newlines: bool = True):
        self._embedder = embedder
        self.replace_newlines = replace_newlines
        self.name = f"adaptive_testing.embedders.EmbedderAdapter({embedder.model_name}):"

    def __call__(self, strings: List[str]) -> np.ndarray:
        """Generate embeddings for a list of strings.

        Args:
            strings: List of text strings to embed

        Returns:
            2D numpy array of shape (len(strings), embedding_dim)
        """
        if len(strings) == 0:
            return np.array([])

        # Clean strings
        cleaned_strings = []
        for s in strings:
            if s == "":
                s = " "  # Most models don't like empty strings
            elif self.replace_newlines:
                s = s.replace("\n", " ")
            cleaned_strings.append(s)

        embeddings = self._embedder.generate_batch(cleaned_strings)
        return np.vstack(embeddings)


def embed_with_cache(embedder: EmbedderAdapter, strings: List[str], should_normalize: bool = True):
    """Embed strings using the provided embedder with caching.

    Args:
        embedder: An EmbedderAdapter instance wrapping a BaseEmbedder
        strings: List of strings to embed
        should_normalize: Whether to L2-normalize embeddings (default: True)

    Returns:
        List of embedding vectors (numpy arrays)
    """
    text_prefix = embedder.name

    # Find which strings are not in the cache
    new_strings = []
    for s in strings:
        prefixed_s = text_prefix + s
        if prefixed_s not in _embedding_memory_cache:
            if prefixed_s not in _embedding_file_cache:
                new_strings.append(s)
                _embedding_memory_cache[prefixed_s] = None  # placeholder
            else:
                _embedding_memory_cache[prefixed_s] = _embedding_file_cache[prefixed_s]

    # Embed the new strings
    if len(new_strings) > 0:
        new_embeds = embedder(new_strings)
        for i, s in enumerate(new_strings):
            prefixed_s = text_prefix + s
            if should_normalize:
                _embedding_memory_cache[prefixed_s] = new_embeds[i] / np.linalg.norm(new_embeds[i])
            else:
                _embedding_memory_cache[prefixed_s] = new_embeds[i]
            _embedding_file_cache[prefixed_s] = _embedding_memory_cache[prefixed_s]

    return [_embedding_memory_cache[text_prefix + s] for s in strings]


def cos_sim(a, b):
    """Cosine similarity between two vectors."""
    return normalize(a, axis=1) @ normalize(b, axis=1).T
