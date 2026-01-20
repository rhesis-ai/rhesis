from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.capabilities import CapabilityMixin, ModelCapabilities
from rhesis.sdk.models.content import (
    AudioContent,
    ContentPart,
    FileContent,
    ImageContent,
    Message,
    TextContent,
    VideoContent,
)
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.models.providers.gemini import GeminiLLM
from rhesis.sdk.models.providers.litellm import LiteLLM
from rhesis.sdk.models.providers.native import RhesisLLM
from rhesis.sdk.models.providers.openai import OpenAILLM
from rhesis.sdk.models.providers.openrouter import OpenRouterLLM
from rhesis.sdk.models.providers.polyphemus import PolyphemusLLM
from rhesis.sdk.models.providers.vertex_ai import VertexAILLM

try:
    from rhesis.sdk.models.providers.huggingface import HuggingFaceLLM

    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False

__all__ = [
    "BaseLLM",
    "RhesisLLM",
    "LiteLLM",
    "GeminiLLM",
    "VertexAILLM",
    "OpenAILLM",
    "OpenRouterLLM",
    "PolyphemusLLM",
    "get_model",
    # Multimodal content types
    "Message",
    "ContentPart",
    "TextContent",
    "ImageContent",
    "AudioContent",
    "VideoContent",
    "FileContent",
    # Capabilities
    "ModelCapabilities",
    "CapabilityMixin",
]

if HUGGINGFACE_AVAILABLE:
    __all__.append("HuggingFaceLLM")
