from rhesis.sdk.models.base import BaseEmbedder, BaseLLM, BaseModel
from rhesis.sdk.models.factory import (
    ModelType,
    get_available_embedding_models,
    get_available_language_models,
    get_embedder,
    get_embedding_model,
    get_language_model,
    get_model,
)
from rhesis.sdk.models.providers.azure_ai import AzureAILLM
from rhesis.sdk.models.providers.azure_openai import AzureOpenAILLM
from rhesis.sdk.models.providers.gemini import GeminiEmbedder, GeminiLLM
from rhesis.sdk.models.providers.litellm import LiteLLM
from rhesis.sdk.models.providers.litellm_proxy import LiteLLMProxy
from rhesis.sdk.models.providers.native import RhesisLLM
from rhesis.sdk.models.providers.openai import OpenAIEmbedder, OpenAILLM
from rhesis.sdk.models.providers.openrouter import OpenRouterLLM
from rhesis.sdk.models.providers.polyphemus import PolyphemusLLM
from rhesis.sdk.models.providers.vertex_ai import VertexAIEmbedder, VertexAILLM

try:
    from rhesis.sdk.models.providers.huggingface import HuggingFaceLLM

    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False


__all__ = [
    "AzureAILLM",
    "AzureOpenAILLM",
    "BaseEmbedder",
    "BaseLLM",
    "BaseModel",
    "ModelType",
    "GeminiEmbedder",
    "GeminiLLM",
    "LiteLLM",
    "LiteLLMProxy",
    "OpenAIEmbedder",
    "OpenAILLM",
    "OpenRouterLLM",
    "PolyphemusLLM",
    "RhesisLLM",
    "VertexAIEmbedder",
    "VertexAILLM",
    "get_available_embedding_models",
    "get_available_language_models",
    "get_embedder",
    "get_embedding_model",
    "get_language_model",
    "get_model",
]

if HUGGINGFACE_AVAILABLE:
    __all__.append("HuggingFaceLLM")
