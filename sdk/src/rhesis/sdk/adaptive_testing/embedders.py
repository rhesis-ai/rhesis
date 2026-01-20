import appdirs
import diskcache
import numpy as np
from sklearn.preprocessing import normalize

_embedding_memory_cache = {}
_embedding_file_cache = diskcache.Cache(
    appdirs.user_cache_dir("adaptive_testing") + "/embeddings.diskcache"
)


def embed_with_cache(embedder, strings, should_normalize=True):
    """Embed strings using the provided embedder with caching."""
    text_prefix = embedder.name

    # find which strings are not in the cache
    new_strings = []
    for s in strings:
        prefixed_s = text_prefix + s
        if prefixed_s not in _embedding_memory_cache:
            if prefixed_s not in _embedding_file_cache:
                new_strings.append(s)
                _embedding_memory_cache[prefixed_s] = None  # placeholder
            else:
                _embedding_memory_cache[prefixed_s] = _embedding_file_cache[prefixed_s]

    # embed the new strings
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


class OpenAITextEmbedding:
    def __init__(
        self,
        model="text-embedding-3-small",
        api_key=None,
        dimensions=768,
        replace_newlines=True,
    ):
        from rhesis.sdk.models import get_embedder

        self.model = model
        self.dimensions = dimensions
        self.replace_newlines = replace_newlines
        self.model_name = model
        self.name = (
            f"adaptive_testing.embedders.OpenAITextEmbedding({self.model_name},d={dimensions}):"
        )
        # Use SDK embedder
        self._embedder = get_embedder(
            provider="openai",
            model_name=model,
            api_key=api_key,
            dimensions=dimensions,
        )

    def __call__(self, strings):
        if len(strings) == 0:
            return np.array([])

        # clean the strings for OpenAI
        cleaned_strings = []
        for s in strings:
            if s == "":
                s = " "  # because OpenAI doesn't like empty strings
            elif self.replace_newlines:
                s = s.replace("\n", " ")  # OpenAI recommends this for things that are not code
            cleaned_strings.append(s)

        # Use SDK embedder
        embeddings = self._embedder.generate_batch(cleaned_strings)
        return np.vstack(embeddings)
