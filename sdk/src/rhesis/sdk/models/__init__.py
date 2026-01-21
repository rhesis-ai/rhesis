from rhesis.sdk.models.base import BaseEmbedder, BaseLLM
from rhesis.sdk.models.factory import get_embedder, get_model
from rhesis.sdk.models.providers.gemini import GeminiEmbedder, GeminiLLM
from rhesis.sdk.models.providers.litellm import LiteLLM
from rhesis.sdk.models.providers.native import RhesisLLM
from rhesis.sdk.models.providers.openai import OpenAIEmbedder, OpenAILLM
from rhesis.sdk.models.providers.openrouter import OpenRouterLLM
from rhesis.sdk.models.providers.polyphemus import PolyphemusLLM
from rhesis.sdk.models.providers.vertex_ai import VertexAILLM

try:
    from rhesis.sdk.models.providers.huggingface import HuggingFaceLLM

    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False

__all__ = [
    "BaseEmbedder",
    "BaseLLM",
    "GeminiEmbedder",
    "GeminiLLM",
    "LiteLLM",
    "OpenAIEmbedder",
    "OpenAILLM",
    "OpenRouterLLM",
    "PolyphemusLLM",
    "RhesisLLM",
    "VertexAILLM",
    "get_embedder",
    "get_model",
]

if HUGGINGFACE_AVAILABLE:
    __all__.append("HuggingFaceLLM")
