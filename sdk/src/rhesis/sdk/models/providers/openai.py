import os
from typing import Optional

from rhesis.sdk.models.defaults import (
    DEFAULT_EMBEDDING_MODELS,
    DEFAULT_LANGUAGE_MODELS,
    model_name_from_id,
)
from rhesis.sdk.models.providers.litellm import LiteLLM, LiteLLMEmbedder

DEFAULT_MODEL = DEFAULT_LANGUAGE_MODELS["openai"]
DEFAULT_MODEL_NAME = model_name_from_id(DEFAULT_MODEL)
DEFAULT_EMBEDDING_MODEL = model_name_from_id(DEFAULT_EMBEDDING_MODELS["openai"])


class OpenAILLM(LiteLLM):
    PROVIDER = "openai"

    def __init__(self, model_name=DEFAULT_MODEL_NAME, api_key=None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if api_key is None:
            raise ValueError("OPENAI_API_KEY is not set")
        super().__init__(self.PROVIDER + "/" + model_name, api_key=api_key)


class OpenAIEmbedder(LiteLLMEmbedder):
    """OpenAI embedder using text-embedding models.

    Args:
        model_name: The embedding model name (default: "text-embedding-3-small").
        api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY env variable.
        dimensions: Optional embedding dimensions (supported by text-embedding-3-*).

    Usage:
        >>> embedder = OpenAIEmbedder()
        >>> embedding = embedder.generate("Hello, world!")
        >>> embeddings = embedder.generate_batch(["Hello", "World"], dimensions=256)
    """

    PROVIDER = "openai"

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        api_key: Optional[str] = None,
        dimensions: Optional[int] = None,
    ):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if api_key is None:
            raise ValueError("OPENAI_API_KEY is not set")
        super().__init__(
            model_name=self.PROVIDER + "/" + model_name,
            api_key=api_key,
            dimensions=dimensions,
        )
